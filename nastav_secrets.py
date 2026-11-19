"""Nahraje tajné údaje do GitHub Secrets. Spouští uživatel sám ve svém terminálu.

IMAP_USER a IMAP_PASSWORD vezme z Klíčenky Windows a předá rovnou do `gh` (nevypisuje je).
KOKPIT_HESLO se zeptá (nezobrazuje se).
"""
import getpass
import subprocess
import sys

import keyring

try:  # certifikáty z Windows (antivirus kontroluje HTTPS)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

GH = r"C:\Program Files\GitHub CLI\gh.exe"
REPO = "metropolitnidivadlo/email-asistent"
SERVICE = "email-asistent-wedos"


def put(name, value):
    r = subprocess.run([GH, "secret", "set", name, "--repo", REPO], input=value, text=True,
                       capture_output=True)
    print(("OK      " if r.returncode == 0 else "CHYBA   ") + name)
    if r.returncode != 0:
        print(r.stderr.strip())


user = keyring.get_password(SERVICE, "__user__")
pwd = keyring.get_password(SERVICE, user) if user else None
if not user or not pwd:
    sys.exit("V Klíčence chybí údaje. Spusťte nejdřív: python imap_core.py setup")
if "--bez-schranky" not in sys.argv:
    put("IMAP_USER", user)
    put("IMAP_PASSWORD", pwd)

while "--bez-kokpitu" not in sys.argv:
    h1 = getpass.getpass("\nZvolte heslo ke kokpitu (min. 12 znaků, při psaní se nic nezobrazuje): ")
    if len(h1) < 12:
        print(f"Heslo má jen {len(h1)} znaků, potřeba je aspoň 12. Zkuste znovu.")
        continue
    h2 = getpass.getpass("Zopakujte stejné heslo: ")
    if h1 != h2:
        print("Hesla se neshodují. Zkuste znovu.")
        continue
    put("KOKPIT_HESLO", h1)
    break

# Telegram (volitelné – Enter = přeskočit)
tok = getpass.getpass("\nToken Telegram bota od BotFathera (Enter = přeskočit): ").strip()
if tok:
    import json
    import urllib.request
    input("Napište teď svému botovi v Telegramu jakoukoli zprávu (např. Ahoj) a pak stiskněte Enter...")
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/getUpdates", timeout=20) as r:
            upd = json.load(r).get("result", [])
        chat = next((u["message"]["chat"]["id"] for u in reversed(upd) if "message" in u), None)
    except Exception as e:  # noqa: BLE001
        chat = None
        print("Nepodařilo se spojit s Telegramem:", type(e).__name__)
    if chat is None:
        print("Zpráva od vás nenalezena – spusťte skript znovu a botovi nejdřív napište.")
    else:
        put("TELEGRAM_BOT_TOKEN", tok)
        put("TELEGRAM_CHAT_ID", str(chat))
        try:
            data = json.dumps({"chat_id": chat, "text": "✅ E-mailový asistent je napojený."}).encode()
            req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=20)
            print("Zkušební zpráva odeslána do Telegramu.")
        except Exception:  # noqa: BLE001
            pass

# Token předplatného Claude (volitelné)
ct = getpass.getpass("\nToken z `claude setup-token` (Enter = přeskočit): ").strip()
if ct:
    put("CLAUDE_CODE_OAUTH_TOKEN", ct)
print("\nHotovo.")
