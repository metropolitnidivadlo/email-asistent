"""IMAP klient pro schránku WEDOS. Čtení vždy přes BODY.PEEK (nemění \\Seen)."""
import email
import imaplib
import os
import re
import sys
import time
from dataclasses import dataclass, field
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser

from . import config, utf7
from .secrets import get_secret


@dataclass
class Email:
    uid: str
    message_id: str
    from_name: str
    from_addr: str
    to: str
    date: str
    subject: str
    text: str
    list_unsubscribe: str = ""
    precedence: str = ""
    auto_submitted: str = ""
    in_reply_to: str = ""


class _HtmlToText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag in ("p", "div", "tr", "li"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html):
    p = _HtmlToText()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass
    text = "".join(p.parts)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _dec(value):
    try:
        return str(make_header(decode_header(value or "")))
    except Exception:
        return str(value or "")


def _payload(part):
    data = part.get_payload(decode=True) or b""
    try:
        return data.decode(part.get_content_charset() or "utf-8", "replace")
    except LookupError:
        return data.decode("utf-8", "replace")


def body_text(msg):
    parts = list(msg.walk()) if msg.is_multipart() else [msg]
    for p in parts:
        if p.get_content_type() == "text/plain" and not p.get_filename():
            return _payload(p).strip()
    for p in parts:
        if p.get_content_type() == "text/html" and not p.get_filename():
            return html_to_text(_payload(p))
    return ""


def parse_email(uid, raw):
    msg = email.message_from_bytes(raw)
    name, addr = parseaddr(_dec(msg.get("From")))
    try:
        date = parsedate_to_datetime(msg.get("Date")).isoformat()
    except Exception:
        date = str(msg.get("Date") or "")
    return Email(
        uid=str(uid),
        message_id=(msg.get("Message-ID") or "").strip(),
        from_name=name,
        from_addr=addr.lower(),
        to=_dec(msg.get("To")),
        date=date,
        subject=_dec(msg.get("Subject")),
        text=body_text(msg),
        list_unsubscribe=_dec(msg.get("List-Unsubscribe")),
        precedence=(msg.get("Precedence") or "").strip().lower(),
        auto_submitted=(msg.get("Auto-Submitted") or "").strip().lower(),
        in_reply_to=(msg.get("In-Reply-To") or "").strip(),
    )


_QUOTE_END = re.compile(r"^(-{2,}\s*(Original|Původní)|.*\bnapsal(a)?:\s*$|On .* wrote:\s*$)", re.I)


def strip_quotes(text):
    """Odstraní citace (řádky s ">") a vše pod '-----Original' / 'Dne ... napsal'."""
    out = []
    for line in text.splitlines():
        if _QUOTE_END.match(line.strip()):
            break
        if line.lstrip().startswith(">"):
            continue
        out.append(line)
    return "\n".join(out).strip()


_LIST_RE = re.compile(r'\((?P<flags>[^)]*)\)\s+(?P<delim>"(?:[^"\\]|\\.)*"|NIL)\s+(?P<name>.+)$')


class Mailbox:
    def __init__(self, host=config.IMAP_HOST, port=config.IMAP_PORT):
        self.host, self.port = host, port
        self.conn = None
        self.delim = "/"
        self.prefix = ""  # např. "INBOX." pokud server drží složky pod INBOX
        self._folders = None
        self._caps = set()

    # --- spojení ---
    def connect(self):
        user, pwd = get_secret("IMAP_USER"), get_secret("IMAP_PASSWORD")
        if not user or not pwd:
            sys.exit("Chybí IMAP přihlašovací údaje (IMAP_USER/IMAP_PASSWORD nebo Klíčenka; viz imap_core.py setup).")
        self.user = user
        self.conn = imaplib.IMAP4_SSL(self.host, self.port)
        self.conn.login(user, pwd)
        typ, caps = self.conn.capability()
        self._caps = set(caps[0].decode().upper().split()) if typ == "OK" and caps and caps[0] else set()
        return self

    def logout(self):
        try:
            if self.conn:
                self.conn.logout()
        except Exception:
            pass
        self.conn = None

    # --- složky ---
    def list_folders(self, refresh=False):
        if self._folders is not None and not refresh:
            return self._folders
        typ, data = self.conn.list()
        names = []
        for item in data or []:
            if isinstance(item, tuple):  # literál
                names.append(utf7.decode(item[1].decode("ascii", "replace")))
                continue
            if not item:
                continue
            m = _LIST_RE.match(item.decode("ascii", "replace"))
            if not m:
                continue
            if "\\NOSELECT" in m.group("flags").upper():
                continue
            if m.group("delim") != "NIL":
                self.delim = m.group("delim").strip('"')
            name = m.group("name").strip()
            if name.startswith('"') and name.endswith('"'):
                name = name[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            names.append(utf7.decode(name))
        self._folders = names
        if any(n.startswith("INBOX" + self.delim) for n in names) and not any(
                n.startswith("Sent") for n in names):
            self.prefix = "INBOX" + self.delim
        return names

    def resolve(self, name):
        """Skutečný název složky na serveru (s případným prefixem INBOX.), nebo None."""
        folders = self.list_folders()
        for cand in (name, self.prefix + name, "INBOX" + self.delim + name):
            if cand in folders:
                return cand
        low = name.lower()
        for f in folders:
            if f.split(self.delim)[-1].lower() == low:
                return f
        return None

    def ensure_folders(self, names, create=True):
        """Vrátí seznam chybějících složek; pokud create, pokusí se je vytvořit."""
        missing = [n for n in names if self.resolve(n) is None]
        if not create:
            return missing
        still = []
        for n in missing:
            real = self.prefix + n
            typ, _ = self.conn.create(self._q(real))
            if typ == "OK":
                try:
                    self.conn.subscribe(self._q(real))
                except Exception:
                    pass
            else:
                still.append(n)
        self.list_folders(refresh=True)
        return still

    @staticmethod
    def _q(name):
        enc = utf7.encode(name).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{enc}"'

    def _select(self, folder, readonly):
        real = self.resolve(folder) or folder
        typ, data = self.conn.select(self._q(real), readonly=readonly)
        if typ != "OK":
            raise RuntimeError(f"Složku '{folder}' nelze otevřít")
        return real

    # --- čtení ---
    def _fetch_uids(self, uids):
        out = []
        for uid in uids:
            typ, data = self.conn.uid("FETCH", uid, "(BODY.PEEK[])")
            if typ != "OK" or not data or not isinstance(data[0], tuple):
                continue
            out.append(parse_email(uid.decode() if isinstance(uid, bytes) else uid, data[0][1]))
        return out

    def _search(self, *criteria):
        typ, data = self.conn.uid("SEARCH", None, *criteria)
        return data[0].split() if typ == "OK" and data and data[0] else []

    def fetch_latest(self, folder="INBOX", n=10):
        self._select(folder, readonly=True)
        return self._fetch_uids(self._search("ALL")[-n:])

    def fetch_unprocessed(self, folder="INBOX"):
        self._select(folder, readonly=False)
        # Pojistka: jen zprávy novější než bod spuštění (ASISTENT_OD_UID). Bez něj nic.
        od = os.environ.get("ASISTENT_OD_UID", "").strip()
        if not od.isdigit():
            print("ASISTENT_OD_UID není nastaveno – nic se nezpracuje.")
            return []
        uids = [u for u in self._search("UNKEYWORD", config.DONE_KEYWORD) if int(u) > int(od)]
        return self._fetch_uids(uids)

    def fetch_sent_samples(self, n=30):
        texts = []
        for name in config.SENT_FOLDERS:
            if self.resolve(name) is None:
                continue
            try:
                self._select(name, readonly=True)
            except RuntimeError:
                continue
            for e in reversed(self._fetch_uids(self._search("ALL")[-n:])):
                t = strip_quotes(e.text)
                if t:
                    texts.append(t)
            if texts:
                break
        return texts[:n]

    # --- změny (jen v ostrém režimu) ---
    def add_flag(self, uid, keyword):
        typ, _ = self.conn.uid("STORE", uid, "+FLAGS", f"({keyword})")
        if typ != "OK":
            print(f"  [IMAP] nepodařilo se nastavit příznak {keyword} u UID {uid}", file=sys.stderr)
        return typ == "OK"

    def move(self, uid, folder):
        real = self.resolve(folder) or (self.prefix + folder)
        dest = self._q(real)
        if "MOVE" in self._caps:
            typ, _ = self.conn.uid("MOVE", uid, dest)
            if typ == "OK":
                return True
        typ, _ = self.conn.uid("COPY", uid, dest)
        if typ != "OK":
            print(f"  [IMAP] kopie UID {uid} do '{folder}' selhala", file=sys.stderr)
            return False
        if "UIDPLUS" in self._caps:
            self.conn.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
            self.conn.uid("EXPUNGE", uid)
            return True
        # Bez UIDPLUS nelze bezpečně smazat jen jednu zprávu: zůstane kopie v INBOX s příznakem.
        self.add_flag(uid, config.DONE_KEYWORD)
        print(f"  [IMAP] server nemá MOVE ani UIDPLUS; UID {uid} jen zkopírováno do '{folder}', "
              f"originál zůstal v INBOX s příznakem {config.DONE_KEYWORD}", file=sys.stderr)
        return True

    def copy(self, uid, folder):
        """Zkopíruje zprávu do složky; originál zůstává v Doručené poště."""
        real = self.resolve(folder) or (self.prefix + folder)
        typ, _ = self.conn.uid("COPY", uid, self._q(real))
        if typ != "OK":
            print(f"  [IMAP] kopie UID {uid} do '{folder}' selhala", file=sys.stderr)
            return False
        return True

    def append_draft(self, folder, msg: EmailMessage):
        real = self.resolve(folder) or (self.prefix + folder)
        typ, _ = self.conn.append(self._q(real), "(\\Draft \\Seen)",
                                  imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        return typ == "OK"
