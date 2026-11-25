"""Synchronizace příznaků přečteno (\\Seen) a odpovězeno (\\Answered) z Doručené pošty na kopie ve složkách.

Originál je v INBOX, asistent dělá kopii do tematické složky. Uživatel pracuje v INBOX,
takže stav originálu se zrcadlí na kopii (oběma směry: přidat i odebrat). Kopie se páruje
podle Message-ID; zpracovávají se jen zprávy asistenta ($AsistentHotovo) za posledních DNI dní.
"""
import re
import sys
from datetime import date, timedelta

from . import config

PRIZNAKY = ("\\Seen", "\\Answered")
DNI = 45
_MESICE = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _since(dni):
    d = date.today() - timedelta(days=dni)
    return f"{d.day}-{_MESICE[d.month - 1]}-{d.year}"


def parse_fetch(data):
    """Z odpovědi FETCH (UID FLAGS BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)]) vrátí {message_id: (uid, {flags})}."""
    out = {}
    for part in data or []:
        if not isinstance(part, tuple):
            continue
        meta = part[0].decode("ascii", "replace")
        m_uid = re.search(r"UID (\d+)", meta)
        m_fl = re.search(r"FLAGS \(([^)]*)\)", meta)
        hdr = part[1].decode("utf-8", "replace")
        m_id = re.search(r"Message-ID:\s*(<[^>]+>)", hdr, re.I)
        if m_uid and m_id:
            flags = {f for f in (m_fl.group(1).split() if m_fl else []) if f in PRIZNAKY}
            out[m_id.group(1)] = (m_uid.group(1), flags)
    return out


def rozdil(zdroj, cil):
    """Vrátí (přidat, odebrat) – sady příznaků, aby cíl odpovídal zdroji."""
    return zdroj - cil, (cil - zdroj) & set(PRIZNAKY)


def _nacti(mb, slozka):
    mb._select(slozka, readonly=(slozka == "INBOX"))
    uids = mb._search("KEYWORD", config.DONE_KEYWORD, "SINCE", _since(DNI))
    out = {}
    for i in range(0, len(uids), 100):
        chunk = b",".join(uids[i:i + 100]).decode()
        typ, data = mb.conn.uid("FETCH", chunk, "(UID FLAGS BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
        if typ == "OK":
            out.update(parse_fetch(data))
    return out


def synchronizuj(mb):
    """Zrcadlí \\Seen a \\Answered z INBOX na kopie. Vrátí počet upravených kopií. Chyby jen loguje."""
    try:
        inbox = _nacti(mb, "INBOX")
    except Exception as e:  # noqa: BLE001
        print(f"Příznaky: INBOX nelze načíst ({type(e).__name__})", file=sys.stderr)
        return 0
    zmeneno = 0
    for slozka in config.FOLDERS:
        if mb.resolve(slozka) is None:
            continue
        try:
            kopie = _nacti(mb, slozka)
            for mid, (uid, flags) in kopie.items():
                if mid not in inbox:
                    continue  # originál v INBOX smazán/přesunut – kopii nechat být
                pridat, odebrat = rozdil(inbox[mid][1], flags)
                if pridat:
                    mb.conn.uid("STORE", uid, "+FLAGS", "(" + " ".join(sorted(pridat)) + ")")
                if odebrat:
                    mb.conn.uid("STORE", uid, "-FLAGS", "(" + " ".join(sorted(odebrat)) + ")")
                if pridat or odebrat:
                    zmeneno += 1
        except Exception as e:  # noqa: BLE001
            print(f"Příznaky: složka '{slozka}' přeskočena ({type(e).__name__})", file=sys.stderr)
    print(f"Příznaky: upraveno {zmeneno} kopií.")
    return zmeneno
