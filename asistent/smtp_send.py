"""Odeslání e-mailu přes SMTP (WEDOS). Používá se JEN pro koncept schválený v Telegramu (dvojí potvrzení)."""
import base64
import os
import smtplib
import ssl
import sys

from . import config
from .secrets import get_secret

SMTP_PORT = 465


def smtp_host():
    return os.environ.get("SMTP_HOST") or "wes1-smtp.wedos.net"


def _login():
    user, pwd = get_secret("IMAP_USER"), get_secret("IMAP_PASSWORD")
    if not user or not pwd:
        raise RuntimeError("chybí přihlašovací údaje")
    smtp = smtplib.SMTP_SSL(smtp_host(), SMTP_PORT, local_hostname="localhost", timeout=30, context=ssl.create_default_context())
    try:
        # smtplib.login kóduje údaje jako ASCII; AUTH PLAIN ručně v UTF-8 (hesla s diakritikou/speciálními znaky)
        smtp.ehlo()
        token = base64.b64encode(f"\0{user}\0{pwd}".encode("utf-8")).decode("ascii")
        code, _ = smtp.docmd("AUTH", "PLAIN " + token)
        if code != 235:
            raise smtplib.SMTPAuthenticationError(code, "autentizace odmítnuta")
    except Exception:
        try:
            smtp.close()
        except Exception:
            pass
        raise
    return smtp


def check_login():
    """Jen přihlášení a odhlášení, nic se neodesílá. Vrací True/False."""
    try:
        smtp = _login()
        smtp.quit()
        return True
    except Exception as e:
        print(f"SMTP přihlášení selhalo ({type(e).__name__})", file=sys.stderr)
        return False


def save_sent_copy(mb, msg):
    """APPEND kopie do první existující odeslané složky s \\Seen. Chyba nevadí (mail už odešel)."""
    from .souhrny import append_seen
    try:
        for name in config.SENT_FOLDERS:
            if mb.resolve(name) is not None:
                return append_seen(mb, name, msg)
    except Exception as e:
        print(f"  [IMAP] uložení kopie do odeslaných selhalo ({type(e).__name__})", file=sys.stderr)
    return False


def send(msg, mb=None):
    """Odešle EmailMessage (příjemci z To/Cc/Bcc). Při chybě vyhodí výjimku. mb: Mailbox pro kopii do odeslaných."""
    smtp = _login()
    try:
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    if mb is not None:
        save_sent_copy(mb, msg)
