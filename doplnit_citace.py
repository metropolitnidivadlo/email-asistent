"""Doplní citaci původního mailu do čekajících konceptů asistenta (s hlavičkou X-Asistent-Id).

  python doplnit_citace.py            # jen vypíše, co by se změnilo
  python doplnit_citace.py --provest  # nahradí koncept novou verzí s citací (stejné X-Asistent-Id)
Koncepty bez X-Asistent-Id (vaše vlastní) nechává být.
"""
import email
import email.policy
import re
import sys
import time
import imaplib

from asistent import config, drafts
from asistent.imap_client import Mailbox, parse_email

SEP = "________________________________"
provest = "--provest" in sys.argv
mb = Mailbox()
mb.connect()


def najdi_original(mid):
    for slozka in ["INBOX"] + list(config.FOLDERS):
        if mb.resolve(slozka) is None and slozka != "INBOX":
            continue
        mb._select(slozka, readonly=True)
        uids = mb._search("HEADER", "Message-ID", f"\"{mid}\"")
        if uids:
            typ, data = mb.conn.uid("FETCH", uids[-1], "(BODY.PEEK[])")
            if typ == "OK" and isinstance(data[0], tuple):
                return parse_email(uids[-1].decode(), data[0][1])
    return None


mb._select(config.FOLDER_DRAFTS, readonly=True)
kandidati = []
for uid in mb._search("HEADER", "X-Asistent-Id", "\"\""):
    typ, data = mb.conn.uid("FETCH", uid, "(BODY.PEEK[])")
    if typ != "OK" or not isinstance(data[0], tuple):
        continue
    msg = email.message_from_bytes(data[0][1], policy=email.policy.default)
    body = msg.get_body(("plain",))
    text = body.get_content() if body else ""
    if SEP in text:
        continue
    kandidati.append((uid, msg, text))

print(f"Konceptů bez citace: {len(kandidati)}")
for uid, msg, text in kandidati:
    irt = (msg.get("In-Reply-To") or "").strip()
    orig = najdi_original(irt) if irt else None
    print(f"- {msg.get('Subject')}  -> původní mail {'nalezen' if orig else 'NENALEZEN'}")
    if not (provest and orig):
        continue
    msg.set_content(text.rstrip() + "\n\n" + drafts.citace(orig))
    real = mb.resolve(config.FOLDER_DRAFTS)
    mb._select(config.FOLDER_DRAFTS, readonly=False)
    typ, _ = mb.conn.append(mb._q(real), "(\\Draft \\Seen)",
                            imaplib.Time2Internaldate(time.time()), msg.as_bytes())
    if typ == "OK":
        mb.conn.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
        mb.conn.uid("EXPUNGE", uid)
        print("   nahrazeno")
mb.logout()
