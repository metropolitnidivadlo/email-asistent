"""Přístup ke schránce WEDOS přes IMAP.

Heslo je uložené v Klíčence Windows (Správce pověření), nikdy v kódu.

  python imap_core.py setup            # zadáte e-mail a heslo (heslo se nezobrazuje)
  python imap_core.py test             # ověří přihlášení a vypíše složky
  python imap_core.py find honzx       # najde e-maily od odesílatele (jen čte)
"""
import email
import getpass
import imaplib
import sys
from email.header import decode_header, make_header

import keyring

HOST = "wes1-imap.wedos.net"
PORT = 993
SERVICE = "email-asistent-wedos"


def get_credentials():
    user = keyring.get_password(SERVICE, "__user__")
    pwd = keyring.get_password(SERVICE, user) if user else None
    if not user or not pwd:
        sys.exit("Chybí přihlašovací údaje. Spusťte: python imap_core.py setup")
    return user, pwd


def connect():
    user, pwd = get_credentials()
    conn = imaplib.IMAP4_SSL(HOST, PORT)
    conn.login(user, pwd)
    return conn


def setup():
    user = input("E-mailová adresa (WEDOS): ").strip()
    pwd = getpass.getpass("Heslo (nezobrazuje se): ")
    conn = imaplib.IMAP4_SSL(HOST, PORT)
    try:
        conn.login(user, pwd)
    except imaplib.IMAP4.error as e:
        sys.exit(f"Přihlášení selhalo, nic se neuložilo: {e}")
    conn.logout()
    keyring.set_password(SERVICE, "__user__", user)
    keyring.set_password(SERVICE, user, pwd)
    print("Přihlášení OK. Údaje uloženy do Klíčenky Windows.")


def _decode(value):
    return str(make_header(decode_header(value or "")))


def _body_text(msg):
    parts = list(msg.walk()) if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_type() == "text/plain" and not part.get_filename():
            payload = part.get_payload(decode=True) or b""
            return payload.decode(part.get_content_charset() or "utf-8", "replace")
    for part in parts:
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True) or b""
            return "[HTML] " + payload.decode(part.get_content_charset() or "utf-8", "replace")
    return ""


def list_folders(conn):
    _, data = conn.list()
    return [line.decode().split(' "/" ')[-1].strip('"') for line in data]


def test():
    conn = connect()
    print("Přihlášení OK. Složky:")
    for name in list_folders(conn):
        print("  -", name)
    conn.logout()


def find(sender):
    conn = connect()
    found = 0
    for folder in list_folders(conn):
        if conn.select(f'"{folder}"', readonly=True)[0] != "OK":
            continue
        _, ids = conn.search(None, "FROM", f'"{sender}"')
        for num in ids[0].split()[-5:]:
            _, data = conn.fetch(num, "(BODY.PEEK[])")
            msg = email.message_from_bytes(data[0][1])
            found += 1
            print("=" * 70)
            print("Složka: ", folder)
            print("Od:     ", _decode(msg["From"]))
            print("Datum:  ", msg["Date"])
            print("Předmět:", _decode(msg["Subject"]))
            print("-" * 70)
            print(_body_text(msg)[:4000])
    conn.logout()
    print(f"\nNalezeno: {found}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test"
    if cmd == "setup":
        setup()
    elif cmd == "find" and len(sys.argv) > 2:
        find(sys.argv[2])
    else:
        test()
