"""Nastavení asistenta."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

IMAP_HOST = os.environ.get("IMAP_HOST", "wes1-imap.wedos.net")
IMAP_PORT = 993

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# Cílové složky a jejich popis pro klasifikátor
FOLDERS = {
    "Představení a zájezdy": "hraní, termíny, zájezdy, technické rideri, herci",
    "Doprava": "autobusy, řidiči, přeprava lidí a kulis, ubytování na cestě",
    "Nabídky a objednávky": "poptávky a objednávky představení, nabídky spolupráce",
    "Faktury a finance": "faktury, platby, upomínky, banka, rozpočty",
    "Ostatní": "vše ostatní (včetně vstupenek a prodeje)",
    "Newslettery": "hromadné maily, reklamy, automatické notifikace - jen přesunout, žádný koncept",
}
FOLDER_NEWSLETTER = "Newslettery"
FOLDER_OTHER = "Ostatní"
FOLDER_DRAFTS = "Koncepty"
SENT_FOLDERS = ["Odeslané položky", "Sent Items"]

DONE_KEYWORD = "$AsistentHotovo"

MODEL = os.environ.get("ASISTENT_MODEL") or "claude-haiku-5-5"

# Časové okno běhu (včetně začátku, bez konce)
TZ_NAME = "Europe/Prague"
WINDOW_START = 7
WINDOW_END = 22


def _eu_dst(utc_now):
    """Záložní výpočet letního času EU, když chybí tzdata."""
    def last_sunday(year, month):
        d = datetime(year, month + 1, 1, 1, tzinfo=timezone.utc) if month < 12 else None
        d -= timedelta(days=1)
        d = d.replace(hour=1, minute=0)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    y = utc_now.year
    return last_sunday(y, 3) <= utc_now < last_sunday(y, 10)


def now_prague():
    """Aktuální čas v Praze; bez tzdata záložní výpočet."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(TZ_NAME))
    except Exception:
        utc = datetime.now(timezone.utc)
        off = 2 if _eu_dst(utc) else 1
        return utc.astimezone(timezone(timedelta(hours=off)))


def in_time_window(now=None):
    now = now or now_prague()
    return WINDOW_START <= now.hour < WINDOW_END
