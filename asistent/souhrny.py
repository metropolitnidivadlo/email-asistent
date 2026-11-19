"""Souhrny a úkoly uložené jako zprávy v soukromých složkách schránky (JSON blok v těle zprávy)."""
import imaplib
import json
import re
import sys
import time
from datetime import datetime, timedelta
from email import message_from_bytes
from email.message import EmailMessage

from . import config

JSON_START = "---JSON---"
JSON_END = "---/JSON---"
_BLOCK_RE = re.compile(re.escape(JSON_START) + r"\s*(.*?)\s*" + re.escape(JSON_END), re.S)

PRIORITY = ("vysoká", "střední", "nízká")
MAX_UKOLU = 30
MAX_TEXT = 300


# --- JSON blok ---
def build_block(obj):
    return f"{JSON_START}\n{json.dumps(obj, ensure_ascii=False, indent=2)}\n{JSON_END}"


def parse_block(text):
    """Vrátí poslední platný JSON blok z textu, jinak None."""
    for m in reversed(list(_BLOCK_RE.finditer(text or ""))):
        try:
            return json.loads(m.group(1))
        except ValueError:
            continue
    return None


# --- zprávy ---
def _stamp(now=None):
    return (now or config.now_prague()).strftime("%Y-%m-%d %H:%M")


def build_message(user, subject, body, now=None):
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = user
    msg["Subject"] = subject
    msg["Date"] = (now or config.now_prague()).strftime("%a, %d %b %Y %H:%M:%S %z")
    msg.set_content(body, charset="utf-8")
    return msg


def append_seen(mb, folder, msg):
    """APPEND s příznakem \\Seen. Vrací True/False, nikdy nevyhodí výjimku."""
    try:
        real = mb.resolve(folder) or (mb.prefix + folder)
        typ, _ = mb.conn.append(mb._q(real), "(\\Seen)", imaplib.Time2Internaldate(time.time()),
                                msg.as_bytes())
        return typ == "OK"
    except Exception as e:
        print(f"  [IMAP] uložení do '{folder}' selhalo ({type(e).__name__})", file=sys.stderr)
        return False


def _body(raw):
    msg = message_from_bytes(raw)
    part = next((p for p in (msg.walk() if msg.is_multipart() else [msg])
                 if p.get_content_type() == "text/plain"), None)
    if part is None:
        return ""
    data = part.get_payload(decode=True) or b""
    try:
        return data.decode(part.get_content_charset() or "utf-8", "replace")
    except LookupError:
        return data.decode("utf-8", "replace")


def read_blocks(mb, folder, since=None, last_only=False):
    """Readonly (BODY.PEEK) načte JSON bloky ze zpráv složky. Seřazeno od nejstarší po nejnovější."""
    if mb.resolve(folder) is None:
        return []
    mb._select(folder, readonly=True)
    if since:
        uids = mb._search("SINCE", f"{since.day:02d}-"
                          f"{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][since.month - 1]}"
                          f"-{since.year}")
    else:
        uids = mb._search("ALL")
    if last_only:
        uids = uids[-1:]
    out = []
    for uid in uids:
        typ, data = mb.conn.uid("FETCH", uid, "(BODY.PEEK[])")
        if typ != "OK" or not data or not isinstance(data[0], tuple):
            continue
        block = parse_block(_body(data[0][1]))
        if block is not None:
            out.append(block)
    return out


# --- souhrn z ostrého běhu ---
def build_summary(results, now=None):
    now = now or config.now_prague()
    zpravy = [{"uid": r.get("uid", ""), "datum": r.get("datum", ""), "od": r.get("od", ""),
               "predmet": r.get("predmet", ""), "slozka": r.get("folder", ""),
               "dulezite": bool(r.get("important")), "odpoved": bool(r.get("needs_reply")),
               "shrnuti": r.get("summary", ""), "koncept": bool(r.get("koncept"))} for r in results]
    obj = {"cas": now.isoformat(timespec="minutes"), "pocet": len(zpravy), "zpravy": zpravy}
    lines = [f"Souhrn {_stamp(now)}: zpracováno {len(zpravy)} zpráv, "
             f"důležitých {sum(z['dulezite'] for z in zpravy)}, "
             f"konceptů {sum(z['koncept'] for z in zpravy)}.", ""]
    for z in zpravy:
        mark = "! " if z["dulezite"] else "- "
        lines.append(f"{mark}{z['od']}: {z['predmet']} -> {z['slozka']}"
                     + (f" ({z['shrnuti']})" if z["shrnuti"] else ""))
    lines += ["", build_block(obj), ""]
    return obj, "\n".join(lines)


def save_summary(mb, results, now=None):
    """Uloží souhrn do FOLDER_SOUHRNY. Selhání jen zaloguje."""
    try:
        now = now or config.now_prague()
        _, body = build_summary(results, now)
        msg = build_message(mb.user, f"Souhrn {_stamp(now)}", body, now)
        ok = append_seen(mb, config.FOLDER_SOUHRNY, msg)
        if not ok:
            print("  [souhrn] uložení souhrnu se nepodařilo", file=sys.stderr)
        return ok
    except Exception as e:
        print(f"  [souhrn] uložení souhrnu selhalo ({type(e).__name__})", file=sys.stderr)
        return False


# --- úkoly ---
def validate_tasks(data):
    """Vrátí (čistý_objekt, chyby). Při chybách je objekt None."""
    err = []
    if not isinstance(data, dict):
        return None, ["Kořen musí být objekt."]
    ukoly = data.get("ukoly")
    if not isinstance(ukoly, list):
        return None, ["Pole 'ukoly' musí být seznam."]
    if len(ukoly) > MAX_UKOLU:
        err.append(f"Příliš mnoho úkolů ({len(ukoly)} > {MAX_UKOLU}).")
    clean = []
    for i, u in enumerate(ukoly, 1):
        if not isinstance(u, dict):
            err.append(f"Úkol {i}: musí být objekt.")
            continue
        text = u.get("text")
        if not isinstance(text, str) or not text.strip():
            err.append(f"Úkol {i}: chybí text.")
            continue
        if len(text) > MAX_TEXT:
            err.append(f"Úkol {i}: text je delší než {MAX_TEXT} znaků.")
        termin = u.get("termin")
        if termin is not None:
            try:
                if not isinstance(termin, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", termin):
                    raise ValueError
                datetime.strptime(termin, "%Y-%m-%d")
            except ValueError:
                err.append(f"Úkol {i}: termín musí být YYYY-MM-DD nebo null.")
        prio = u.get("priorita")
        if prio not in PRIORITY:
            err.append(f"Úkol {i}: priorita musí být jedna z {', '.join(PRIORITY)}.")
        zdroj = u.get("zdroj")
        if zdroj is not None and not isinstance(zdroj, str):
            err.append(f"Úkol {i}: zdroj musí být text nebo null.")
        clean.append({"text": text.strip(), "termin": termin, "priorita": prio, "zdroj": zdroj})
    for k in ("vytvoreno", "poznamka"):
        if data.get(k) is not None and not isinstance(data.get(k), str):
            err.append(f"Pole '{k}' musí být text.")
    if err:
        return None, err
    return {"vytvoreno": data.get("vytvoreno"), "ukoly": clean, "poznamka": data.get("poznamka")}, []


def sort_tasks(ukoly):
    """Vysoká priorita nahoře, uvnitř podle termínu (bez termínu naposled)."""
    return sorted(ukoly, key=lambda u: (PRIORITY.index(u["priorita"]) if u.get("priorita") in PRIORITY else 9,
                                        u.get("termin") or "9999-99-99"))


def format_tasks(ukoly, poznamka=None):
    lines = []
    for u in sort_tasks(ukoly):
        t = f" (do {u['termin']})" if u.get("termin") else ""
        z = f" [{u['zdroj']}]" if u.get("zdroj") else ""
        lines.append(f"[{u['priorita']}] {u['text']}{t}{z}")
    if poznamka:
        lines += ["", f"Poznámka: {poznamka}"]
    return "\n".join(lines)


def build_tasks_message(obj, user, now=None):
    now = now or config.now_prague()
    body = (f"Úkoly {_stamp(now)}: {len(obj['ukoly'])}\n\n" + (format_tasks(obj["ukoly"], obj.get("poznamka"))
            or "Žádné úkoly.") + "\n\n" + build_block(obj) + "\n")
    return build_message(user, f"Úkoly {_stamp(now)}", body, now)


def telegram_text(obj):
    if not obj["ukoly"]:
        return "Úkoly: žádné."
    return f"Úkoly ({len(obj['ukoly'])}):\n" + format_tasks(obj["ukoly"], obj.get("poznamka"))


def read_latest_tasks(mb):
    """Poslední uložený objekt úkolů z FOLDER_UKOLY (readonly) nebo None."""
    try:
        blocks = read_blocks(mb, config.FOLDER_UKOLY, last_only=True)
    except Exception:
        return None
    return blocks[-1] if blocks and isinstance(blocks[-1], dict) else None


def since_days(days, now=None):
    return ((now or config.now_prague()) - timedelta(days=max(days, 0))).date()
