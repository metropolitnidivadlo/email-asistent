"""Data pro kokpit. Jen čtení (readonly SELECT, BODY.PEEK hlaviček), žádný stav, žádná těla zpráv."""
import email
import json
import re
from collections import Counter
from datetime import datetime, timedelta
from email.utils import parseaddr, parsedate_to_datetime

from . import config
from .imap_client import _dec

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_FIELDS = "DATE FROM TO SUBJECT MESSAGE-ID IN-REPLY-TO"
LATEST_N = 15
MAX_PER_FOLDER = 400
MAX_DRAFTS = 50
PREVIEW_MAX = 600
DAYS = 30


def _imap_date(d):
    return f"{d.day:02d}-{_MONTHS[d.month - 1]}-{d.year}"


def _parse_headers(raw, flags=""):
    msg = email.message_from_bytes(raw)
    try:
        dt = parsedate_to_datetime(msg.get("Date"))
    except Exception:
        dt = None
    if dt is None:  # koncepty bez hlavičky Date (starší verze asistenta) – ber jako teď
        from datetime import datetime, timezone
        dt = datetime.now(timezone.utc)
    name, addr = parseaddr(_dec(msg.get("From")))
    return {
        "dt": dt, "name": name.strip(), "addr": addr.lower(), "subject": _dec(msg.get("Subject")).strip(),
        "to": _dec(msg.get("To")).strip(), "message_id": (msg.get("Message-ID") or "").strip(),
        "in_reply_to": (msg.get("In-Reply-To") or "").strip(),
        "flagged": "\\FLAGGED" in flags.upper(),
    }


def _fetch_headers(mb, uids, tz):
    """Hlavičky a příznaky přes BODY.PEEK (nemění \\Seen)."""
    out = []
    for i in range(0, len(uids), 100):
        chunk = b",".join(uids[i:i + 100]).decode()
        typ, data = mb.conn.uid("FETCH", chunk, f"(FLAGS BODY.PEEK[HEADER.FIELDS ({_FIELDS})])")
        if typ != "OK":
            continue
        last = None
        for item in data or []:
            if isinstance(item, tuple):
                meta = item[0].decode("ascii", "replace")
                m = re.search(r"FLAGS \(([^)]*)\)", meta)
                last = _parse_headers(item[1], m.group(1) if m else "")
                if last:
                    last["dt"] = last["dt"].astimezone(tz)
                    out.append(last)
            elif isinstance(item, bytes) and last is not None:  # příznaky mohou přijít za literálem
                m = re.search(r"FLAGS \(([^)]*)\)", item.decode("ascii", "replace"))
                if m and "\\FLAGGED" in m.group(1).upper():
                    last["flagged"] = True
    return out


def _read_folder(mb, name, since, tz, limit=MAX_PER_FOLDER):
    """Zprávy ze složky od data `since`; chybějící/nedostupná složka = prázdný seznam."""
    if mb.resolve(name) is None:
        return []
    try:
        mb._select(name, readonly=True)
        uids = mb._search("SINCE", _imap_date(since))[-limit:]
        return _fetch_headers(mb, uids, tz)
    except Exception:
        return []


def _norm_subject(s):
    return re.sub(r"^\s*((re|fw|fwd|odp|vs)\s*:\s*)+", "", (s or ""), flags=re.I).strip().lower()


def _fetch_drafts(mb, uids, tz):
    """Koncepty včetně náhledu textu (BODY.PEEK[], plain text, prvních PREVIEW_MAX znaků); nic neoznačuje."""
    from .imap_client import body_text
    out = []
    for uid in uids:
        try:
            typ, data = mb.conn.uid("FETCH", uid, "(FLAGS BODY.PEEK[])")
            if typ != "OK" or not data or not isinstance(data[0], tuple):
                continue
            meta = data[0][0].decode("ascii", "replace")
            m = re.search(r"FLAGS \(([^)]*)\)", meta)
            h = _parse_headers(data[0][1], m.group(1) if m else "")
            if not h:
                continue
            h["dt"] = h["dt"].astimezone(tz)
            try:
                h["preview"] = body_text(email.message_from_bytes(data[0][1]))[:PREVIEW_MAX]
            except Exception:
                h["preview"] = ""
            out.append(h)
        except Exception:
            continue
    return out


def _short(m, folder=None):
    d = {"date": m["dt"].isoformat(), "from": m["name"] or m["addr"], "addr": m["addr"], "subject": m["subject"]}
    if folder:
        d["folder"] = folder
    return d


def _read_log_important(day, tz):
    """Důležité zprávy dnešního dne z data/log.jsonl (pokud existuje)."""
    path = config.DATA_DIR / "log.jsonl"
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
            dt = datetime.fromisoformat(r["datum"])
        except Exception:
            continue
        if dt.tzinfo is not None:
            dt = dt.astimezone(tz)
        if r.get("important") and dt.date() == day:
            out.append({"date": dt.isoformat(), "from": r.get("od", ""), "addr": r.get("od", ""),
                        "subject": r.get("predmet", ""), "folder": r.get("slozka", ""),
                        "summary": r.get("summary", "")})
    return out


def build(folder_msgs, stat_msgs, drafts, now, reply_hours=None, reply_count=0, important_extra=(),
          own="", source="imap", drafts_total=None):
    """Společné sestavení slovníku. Zprávy: dict(dt, name, addr, subject, flagged)."""
    today, week, month = now.date(), now - timedelta(days=7), now - timedelta(days=DAYS)
    folders = {}
    for name, msgs in folder_msgs.items():
        msgs = sorted(msgs, key=lambda m: m["dt"], reverse=True)
        folders[name] = {
            "today": sum(1 for m in msgs if m["dt"].date() == today),
            "week": sum(1 for m in msgs if m["dt"] >= week),
            "month": sum(1 for m in msgs if m["dt"] >= month),
            "latest": [_short(m) for m in msgs[:LATEST_N]],
        }

    def top(since):
        c, names = Counter(), {}
        for m in stat_msgs:
            if m["dt"] >= since and m["addr"] and m["addr"] != own:
                c[m["addr"]] += 1
                names.setdefault(m["addr"], m["name"])
        return [{"addr": a, "name": names[a], "count": n} for a, n in c.most_common(5)]

    important, seen = [], set()
    for name, msgs in folder_msgs.items():
        for m in msgs:
            if m["dt"].date() == today and m.get("flagged"):
                important.append(_short(m, name))
    important += list(important_extra)
    uniq = []
    for it in sorted(important, key=lambda x: x["date"], reverse=True):
        key = (it["subject"], it["addr"])
        if key not in seen:
            seen.add(key)
            uniq.append(it)

    drafts = sorted(drafts, key=lambda m: m["dt"], reverse=True)
    imp_subj = {_norm_subject(it["subject"]) for it in uniq}
    imp_ids = {m["message_id"] for msgs in folder_msgs.values() for m in msgs
               if m.get("flagged") and m.get("message_id")}

    def draft_important(d):
        return bool(d.get("flagged") or (d.get("in_reply_to") and d["in_reply_to"] in imp_ids)
                    or (d["subject"] and _norm_subject(d["subject"]) in imp_subj))

    return {
        "source": source,
        "generated": now.isoformat(),
        "folders": folders,
        "drafts": {"count": drafts_total if drafts_total is not None else len(drafts),
                   "items": [{"subject": d["subject"], "to": d["to"], "date": d["dt"].isoformat(),
                              "preview": (d.get("preview") or "")[:PREVIEW_MAX],
                              "important": draft_important(d)}
                             for d in drafts[:MAX_DRAFTS]]},
        "top_senders": {"week": top(week), "month": top(month)},
        "reply": {"avg_hours": reply_hours, "count": reply_count},
        "important_today": uniq,
    }


def collect(mb, now=None):
    """Sestaví data kokpitu z IMAP. Jen čtení; nic se nemění ani neoznačuje."""
    now = now or config.now_prague()
    tz = now.tzinfo
    since = (now - timedelta(days=DAYS)).date()
    own = (getattr(mb, "user", "") or "").lower()

    folder_msgs = {}
    for name in ["INBOX"] + list(config.FOLDERS):
        folder_msgs[name] = _read_folder(mb, name, since, tz)

    stat, seen = [], set()
    for msgs in folder_msgs.values():
        for m in msgs:
            key = m["message_id"] or id(m)
            if key not in seen:
                seen.add(key)
                stat.append(m)

    drafts, total = [], 0
    if mb.resolve(config.FOLDER_DRAFTS):
        try:
            mb._select(config.FOLDER_DRAFTS, readonly=True)
            uids = mb._search("ALL")
            total = len(uids)
            drafts = _fetch_drafts(mb, uids[-MAX_DRAFTS:], tz)
            if not drafts and uids:
                drafts = _fetch_headers(mb, uids[-MAX_DRAFTS:], tz)
        except Exception:
            pass

    received = {m["message_id"]: m["dt"] for m in stat if m["message_id"]}
    first_reply = {}
    sent_msgs = []
    for name in config.SENT_FOLDERS:
        for m in _read_folder(mb, name, since, tz):
            sent_msgs.append(m)
            irt = m["in_reply_to"]
            if irt in received and (irt not in first_reply or m["dt"] < first_reply[irt]):
                first_reply[irt] = m["dt"]
    hours = [(sent - received[i]).total_seconds() / 3600 for i, sent in first_reply.items()
             if sent >= received[i]]
    avg = round(sum(hours) / len(hours), 1) if hours else None

    data = build(folder_msgs, stat, drafts, now, avg, len(hours), _read_log_important(now.date(), tz),
                 own, "imap", total)
    data["ukoly"] = _read_ukoly(mb)
    try:
        from . import kontakty
        kont = kontakty.nacist(mb)
        kontakty.oznac_v_kontaktu(kont, kontakty.domeny_zprav(stat + sent_msgs, own))
    except Exception:
        kont = []
    data["kontakty"] = kont
    return data


def _read_ukoly(mb):
    """Poslední zpráva z FOLDER_UKOLY (readonly, BODY.PEEK); chyba = prázdné úkoly."""
    from . import souhrny
    obj = souhrny.read_latest_tasks(mb)
    if not isinstance(obj, dict) or not isinstance(obj.get("ukoly"), list):
        return {"vytvoreno": None, "ukoly": [], "poznamka": None}
    return {"vytvoreno": obj.get("vytvoreno"), "ukoly": [u for u in obj["ukoly"] if isinstance(u, dict)],
            "poznamka": obj.get("poznamka")}


def _fold_name(od):
    name, addr = parseaddr(od or "")
    return name.strip(), addr.lower()


def from_zkouska(path):
    """Stejný slovník ze souboru data/zkouska_ai.json (náhled). 'Dnes' = den nejnovější zprávy."""
    rows = json.loads(open(path, encoding="utf-8").read())
    msgs, drafts = [], []
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["datum"])
        except Exception:
            continue
        name, addr = _fold_name(r.get("od"))
        m = {"dt": dt, "name": name, "addr": addr, "subject": r.get("predmet", ""),
             "flagged": bool(r.get("important")), "folder": r.get("folder") or config.FOLDER_OTHER}
        msgs.append(m)
        if r.get("draft"):
            drafts.append({**m, "to": f"{name} <{addr}>".strip() if name else addr})
    now = max((m["dt"] for m in msgs), default=config.now_prague())
    folder_msgs = {"INBOX": list(msgs)}
    for name in config.FOLDERS:
        folder_msgs[name] = [m for m in msgs if m["folder"] == name]
    data = build(folder_msgs, msgs, drafts, now, None, 0, (), "", "zkouska")
    data["ukoly"] = {"vytvoreno": None, "ukoly": [], "poznamka": None}
    data["kontakty"] = []
    soubor = config.DATA_DIR / "kontakty" / "klienti_cr.csv"
    if soubor.exists():
        from . import kontakty
        data["kontakty"] = kontakty.oznac_v_kontaktu(kontakty.nacist_soubor(soubor), set())
    data["generated"] = config.now_prague().isoformat()
    data["reference_now"] = now.isoformat()
    return data
