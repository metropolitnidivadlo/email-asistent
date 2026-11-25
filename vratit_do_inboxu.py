"""Vrátí do Doručené pošty kopie mailů, které asistent dříve PŘESUNUL do složek.

  python vratit_do_inboxu.py            # jen vypíše, co by se vrátilo
  python vratit_do_inboxu.py --provest  # zkopíruje je zpět do INBOX (ve složkách zůstanou)
Bere jen zprávy s příznakem $AsistentHotovo (zpracované asistentem) a přeskočí ty,
jejichž Message-ID už v INBOX je.
"""
import email
import sys

from asistent import config
from asistent.imap_client import Mailbox

provest = "--provest" in sys.argv
mb = Mailbox()
mb.connect()


def message_ids(uids):
    import re
    ids = {}
    for i in range(0, len(uids), 100):
        chunk = b",".join(u if isinstance(u, bytes) else u.encode() for u in uids[i:i + 100])
        typ, data = mb.conn.uid("FETCH", chunk, "(UID BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT FROM)])")
        if typ != "OK":
            continue
        for part in data:
            if not isinstance(part, tuple):
                continue
            m_uid = re.search(rb"UID (\d+)", part[0])
            if not m_uid:
                continue
            m = email.message_from_bytes(part[1])
            ids[m_uid.group(1)] = ((m.get("Message-ID") or "").strip(), m.get("From", ""), m.get("Subject", ""))
    return ids


mb._select("INBOX", readonly=True)
v_inboxu = {mid for mid, _, _ in message_ids(mb._search("ALL")[-600:]).values() if mid}

celkem = 0
for slozka in config.FOLDERS:
    if mb.resolve(slozka) is None:
        continue
    mb._select(slozka, readonly=not provest)
    uids = mb._search("KEYWORD", config.DONE_KEYWORD)
    k_vraceni = [u for u, (mid, _, _) in message_ids(uids).items() if not mid or mid not in v_inboxu]
    print(f"{slozka}: {len(k_vraceni)} k vrácení")
    celkem += len(k_vraceni)
    if provest and k_vraceni:
        dest = mb._q(mb.resolve("INBOX") or "INBOX")
        for u in k_vraceni:
            typ, _ = mb.conn.uid("COPY", u, dest)
            print("  ", u.decode() if isinstance(u, bytes) else u, "OK" if typ == "OK" else "CHYBA")
print(f"Celkem: {celkem}" + ("" if provest else "  (nanečisto – nic se nezměnilo)"))
mb.logout()
