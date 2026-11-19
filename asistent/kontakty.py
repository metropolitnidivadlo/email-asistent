"""Databáze potenciálních klientů uložená soukromě jako CSV příloha zprávy ve složce FOLDER_KONTAKTY.
(Repo je veřejné, CSV s kontakty v něm být nesmí.)"""
import csv
import io
import re
import sys
from email import message_from_bytes
from email.message import EmailMessage
from email.utils import getaddresses
from urllib.parse import urlparse

from . import config
from .souhrny import append_seen, _stamp

SLOUPCE = ["nazev", "typ", "mesto", "kraj", "web", "email", "telefon", "kontaktni_osoba", "pozice",
           "poznamka", "zdroj_url", "overeno"]
FREEMAIL = {"seznam.cz", "gmail.com", "email.cz", "centrum.cz", "post.cz", "volny.cz", "outlook.com",
            "hotmail.com", "icloud.com"}
PRILOHA = "klienti_cr.csv"


# --- CSV ---
def parse_csv(data):
    """bytes/str -> list dictů (UTF-8 s/bez BOM, oddělovač ';')."""
    if isinstance(data, bytes):
        data = data.decode("utf-8-sig", "replace")
    elif data.startswith("﻿"):
        data = data[1:]
    rows = []
    for r in csv.DictReader(io.StringIO(data), delimiter=";"):
        rows.append({k: (r.get(k) or "").strip() for k in SLOUPCE})
    return [r for r in rows if r["nazev"]]


def nacist_soubor(path):
    with open(path, "rb") as f:
        return parse_csv(f.read())


def pocty(kontakty):
    """(podle kraje, podle typu) jako dicty počtů."""
    kraje, typy = {}, {}
    for k in kontakty:
        kraje[k.get("kraj") or "(bez kraje)"] = kraje.get(k.get("kraj") or "(bez kraje)", 0) + 1
        typy[k.get("typ") or "(bez typu)"] = typy.get(k.get("typ") or "(bez typu)", 0) + 1
    return kraje, typy


# --- zpráva ---
def build_message(user, csv_bytes, now=None):
    now = now or config.now_prague()
    kontakty = parse_csv(csv_bytes)
    kraje, typy = pocty(kontakty)
    s_emailem = sum(1 for k in kontakty if k["email"])
    text = (f"Databáze kontaktů {_stamp(now)}: {len(kontakty)} záznamů, s e-mailem {s_emailem}.\n"
            f"Typy: " + ", ".join(f"{t} {n}" for t, n in sorted(typy.items())) + "\n"
            f"Kraje: " + ", ".join(f"{t} {n}" for t, n in sorted(kraje.items())) + "\n")
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = user
    msg["Subject"] = f"Kontakty {_stamp(now)}"
    msg["Date"] = now.strftime("%a, %d %b %Y %H:%M:%S %z")
    msg.set_content(text, charset="utf-8")
    msg.add_attachment(csv_bytes, maintype="text", subtype="csv", filename=PRILOHA,
                       params={"charset": "utf-8"})
    return msg


def nahrat(mb, csv_path, now=None):
    """Uloží CSV jako novou verzi do FOLDER_KONTAKTY (\\Seen). Vrací (ok, počet záznamů)."""
    with open(csv_path, "rb") as f:
        raw = f.read()
    n = len(parse_csv(raw))
    if n == 0:
        sys.exit(f"Soubor {csv_path} neobsahuje žádné záznamy.")
    mb.ensure_folders([config.FOLDER_KONTAKTY], create=True)
    msg = build_message(mb.user, raw, now)
    return append_seen(mb, config.FOLDER_KONTAKTY, msg), n


def csv_z_prilohy(raw_message):
    """Z bytes celé zprávy vyparsuje CSV přílohu -> list dictů (prázdný, když příloha chybí)."""
    msg = message_from_bytes(raw_message)
    for p in msg.walk():
        name = (p.get_filename() or "").lower()
        if p.get_content_type() == "text/csv" or name.endswith(".csv"):
            return parse_csv(p.get_payload(decode=True) or b"")
    return []


def nacist(mb):
    """Poslední verze z FOLDER_KONTAKTY (readonly, BODY.PEEK). Chyba/nic = []."""
    try:
        if mb.resolve(config.FOLDER_KONTAKTY) is None:
            return []
        mb._select(config.FOLDER_KONTAKTY, readonly=True)
        uids = mb._search("ALL")
        if not uids:
            return []
        uid = max(uids, key=int)
        typ, data = mb.conn.uid("FETCH", uid, "(BODY.PEEK[])")
        if typ != "OK" or not data or not isinstance(data[0], tuple):
            return []
        return csv_z_prilohy(data[0][1])
    except Exception as e:
        print(f"  [kontakty] načtení selhalo ({type(e).__name__})", file=sys.stderr)
        return []


# --- domény a stav "v kontaktu" ---
def domena_adresy(addr):
    addr = (addr or "").strip().lower()
    if "@" not in addr:
        return ""
    return addr.rsplit("@", 1)[1].strip(" >.")


def domena_webu(url):
    url = (url or "").strip().lower()
    if not url:
        return ""
    if "//" not in url:
        url = "//" + url
    host = (urlparse(url).hostname or "").strip(".")
    return host[4:] if host.startswith("www.") else host


def domeny_zprav(msgs, own=""):
    """Množina domén odesílatelů a příjemců (bez freemailů a vlastní domény)."""
    out = set()
    for m in msgs:
        addrs = [m.get("addr", "")] + [a for _, a in getaddresses([m.get("to", "")])]
        for a in addrs:
            d = domena_adresy(a)
            if d:
                out.add(d)
    out -= FREEMAIL
    own_d = domena_adresy(own)
    out.discard(own_d)
    return out


def _shoda(a, b):
    return bool(a) and bool(b) and (a == b or a.endswith("." + b) or b.endswith("." + a))


def oznac_v_kontaktu(kontakty, domeny):
    """Doplní u každého kontaktu v_kontaktu (bool); freemail domény kontaktu se nepočítají."""
    for k in kontakty:
        ds = {domena_adresy(k.get("email")), domena_webu(k.get("web"))} - FREEMAIL - {""}
        k["v_kontaktu"] = any(_shoda(d, z) for d in ds for z in domeny)
    return kontakty
