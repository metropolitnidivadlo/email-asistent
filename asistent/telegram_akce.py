"""Schvalování konceptů v Telegramu. Odeslat se smí JEN koncept, který uživatel dvakrát potvrdil
(send -> sendok). Nic jiného se neodesílá."""
import re
import sys
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

from . import config, smtp_send, telegram

HEADER_ID = "X-Asistent-Id"
ACTIONS = ("send", "sendok", "drop", "back")
_DATA_RE = re.compile(r"^(send|sendok|drop|back):([0-9a-f]{8})$")
CONFIRM_MARK = "\n\n⚠ Opravdu odeslat na "


# --- parsování ---
def parse_callback(data):
    """'send:ab12cd34' -> ('send', 'ab12cd34'); neplatné -> None."""
    m = _DATA_RE.match(data or "")
    return (m.group(1), m.group(2)) if m else None


def extract_actions(updates, chat):
    """Z updates vybere jen callback_query z povoleného chatu. Vrací seznam dictů."""
    out = []
    for u in updates or []:
        cq = u.get("callback_query")
        if not cq:
            continue  # běžné zprávy ignorujeme
        msg = cq.get("message") or {}
        if not chat or str((msg.get("chat") or {}).get("id")) != str(chat):
            continue  # cizí chat
        parsed = parse_callback(cq.get("data"))
        if not parsed:
            continue
        out.append({"action": parsed[0], "id": parsed[1], "callback_id": cq.get("id"),
                    "chat": (msg.get("chat") or {}).get("id"), "message_id": msg.get("message_id"),
                    "text": msg.get("text") or ""})
    return out


# --- odchozí zpráva z konceptu ---
def build_outgoing(raw, from_addr):
    """Z bytes konceptu sestaví EmailMessage k odeslání (bez \\Draft a X-Asistent-Id, nové Date/Message-ID)."""
    src = message_from_bytes(raw, policy=policy.default)
    out = EmailMessage()
    out["From"] = from_addr
    for h in ("To", "Cc", "Bcc", "Subject", "In-Reply-To", "References"):
        if src.get(h):
            out[h] = str(src[h])
    out["Date"] = formatdate(localtime=True)
    domain = from_addr.rsplit("@", 1)[-1] if "@" in from_addr else None
    out["Message-ID"] = make_msgid(domain=domain)
    plain = src.get_body(preferencelist=("plain",))
    html = src.get_body(preferencelist=("html",))
    out.set_content(plain.get_content() if plain is not None else "", charset="utf-8")
    if html is not None:
        out.add_alternative(html.get_content(), subtype="html")
    for att in src.iter_attachments():
        data = att.get_payload(decode=True) or b""
        mt, st = (att.get_content_type() or "application/octet-stream").split("/", 1)
        out.add_attachment(data, maintype=mt, subtype=st, filename=att.get_filename())
    return out


def plain_body(raw):
    part = message_from_bytes(raw, policy=policy.default).get_body(preferencelist=("plain",))
    return part.get_content() if part is not None else ""


# --- práce se schránkou ---
def _q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def find_draft(mb, draft_id):
    """(uid, raw) konceptu s X-Asistent-Id v Koncepty, nebo None."""
    if mb.resolve(config.FOLDER_DRAFTS) is None:
        return None
    mb._select(config.FOLDER_DRAFTS, readonly=False)
    uids = mb._search("HEADER", HEADER_ID, draft_id)
    if not uids:
        return None
    uid = uids[-1]
    typ, data = mb.conn.uid("FETCH", uid, "(BODY.PEEK[])")
    if typ != "OK" or not data or not isinstance(data[0], tuple):
        return None
    return (uid.decode() if isinstance(uid, bytes) else uid), data[0][1]


def delete_draft(mb, uid):
    """\\Deleted + UID EXPUNGE (jen s UIDPLUS; bez něj zůstane jen označený, aby se nesmazaly cizí zprávy)."""
    mb._select(config.FOLDER_DRAFTS, readonly=False)
    typ, _ = mb.conn.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
    if typ != "OK":
        return False
    if "UIDPLUS" in mb._caps:
        mb.conn.uid("EXPUNGE", uid)
    return True


def mark_answered(mb, message_id):
    """Původní mail (podle Message-ID) označí \\Answered ve všech cílových složkách. Chyby nevadí."""
    if not message_id:
        return
    for name in ["INBOX"] + list(config.FOLDERS):
        try:
            if name != "INBOX" and mb.resolve(name) is None:
                continue
            mb._select(name, readonly=False)
            for uid in mb._search("HEADER", "Message-ID", _q(message_id)):
                mb.conn.uid("STORE", uid, "+FLAGS", "(\\Answered)")
        except Exception as e:
            print(f"  [IMAP] označení \\Answered ve '{name}' selhalo ({type(e).__name__})", file=sys.stderr)


# --- zpracování akcí ---
def _recipient(raw):
    to = message_from_bytes(raw, policy=policy.default).get("To") or ""
    return str(to) or parseaddr(to)[1]


def _subject(raw):
    return str(message_from_bytes(raw, policy=policy.default).get("Subject") or "")


def _strip_confirm(text):
    return text.split(CONFIRM_MARK)[0]


def handle(act, mb, nanecisto=False):
    """Zpracuje jednu akci. V režimu nanecisto jen vypíše, co by se stalo."""
    a, did, chat, mid, cid = act["action"], act["id"], act["chat"], act["message_id"], act["callback_id"]
    if nanecisto:
        print(f"  [nanečisto] akce {a} pro koncept {did} (nic se neprovádí)")
        return

    def ans(t=""):
        telegram.answer_callback(cid, t)

    if a == "back":
        telegram.edit_message(chat, mid, _strip_confirm(act["text"]), telegram.keyboard_draft(did))
        return ans()

    found = find_draft(mb, did)
    if found is None:  # idempotence: koncept už neexistuje, nic se neodesílá
        telegram.edit_message(chat, mid, _strip_confirm(act["text"]) + "\n\nKoncept už ve složce není.")
        return ans("Koncept už ve složce není")
    uid, raw = found

    if a == "drop":
        ok = delete_draft(mb, uid)
        telegram.edit_message(chat, mid, "🗑 Zahozeno" if ok else "❌ Zahození selhalo")
        return ans("Zahozeno" if ok else "Chyba")

    if a == "send":
        telegram.edit_message(chat, mid, _strip_confirm(act["text"]) + CONFIRM_MARK + f"{_recipient(raw)}?",
                              [[{"text": "Ano, odeslat", "callback_data": f"sendok:{did}"},
                                {"text": "Zpět", "callback_data": f"back:{did}"}]])
        return ans()

    if a == "sendok":
        to = _recipient(raw)
        if "[DOPLNIT" in plain_body(raw).split("________________________________")[0]:  # jen odpověď, ne citace
            telegram.edit_message(chat, mid, "⚠ Koncept obsahuje [DOPLNIT] a neodeslal se. "
                                  "Doplňte ho v Outlooku a odešlete ručně.")
            return ans("Obsahuje [DOPLNIT]")
        try:
            msg = build_outgoing(raw, mb.user)
            smtp_send.send(msg, mb)
        except Exception as e:
            print(f"  Odeslání konceptu {did} selhalo ({type(e).__name__})", file=sys.stderr)
            telegram.edit_message(chat, mid, "❌ Odeslání selhalo, koncept zůstává v Koncepty")
            return ans("Odeslání selhalo")
        try:
            delete_draft(mb, uid)
        except Exception as e:
            print(f"  Smazání konceptu {did} selhalo ({type(e).__name__})", file=sys.stderr)
        try:
            mark_answered(mb, message_from_bytes(raw, policy=policy.default).get("In-Reply-To"))
        except Exception as e:
            print(f"  Označení \\Answered selhalo ({type(e).__name__})", file=sys.stderr)
        cas = config.now_prague().strftime("%d. %m. %H:%M")
        telegram.edit_message(chat, mid, f"✅ Odesláno {cas} na {to}\nPředmět: {_subject(raw)}")
        return ans("Odesláno")


def run(nanecisto=False):
    """Načte čekající updates, potvrdí je a zpracuje akce z povoleného chatu."""
    from .imap_client import Mailbox
    chat = telegram.chat_id()
    if not chat:
        print("Telegram není nastaven (TELEGRAM_CHAT_ID).")
        return 0
    updates = telegram.get_updates()
    if not updates:
        print("Žádné čekající akce.")
        return 0
    acts = extract_actions(updates, chat)
    print(f"Updates: {len(updates)}, akcí z povoleného chatu: {len(acts)}.")
    if nanecisto:  # nic nepotvrzuje, nic nemění
        for act in acts:
            handle(act, None, nanecisto=True)
        return len(acts)
    # Potvrdit hned (at-most-once): souběžný běh druhého workflow tytéž akce nezopakuje a neodešle dvakrát.
    telegram.get_updates(offset=max(u["update_id"] for u in updates) + 1, limit=1)
    if not acts:
        return 0
    mb = Mailbox().connect()
    try:
        for act in acts:
            try:
                handle(act, mb)
            except Exception as e:
                print(f"  Akce {act['action']} selhala ({type(e).__name__})", file=sys.stderr)
                telegram.answer_callback(act["callback_id"], "Chyba")
    finally:
        mb.logout()
    return len(acts)
