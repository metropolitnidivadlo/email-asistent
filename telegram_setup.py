"""Napojení Telegram bota.

  python telegram_setup.py ulozit     # uživatel vloží token od BotFathera -> Klíčenka Windows
  python telegram_setup.py dokoncit   # najde chat, uloží GitHub Secrets, pošle zkušební zprávu
Token se nikdy nevypisuje.
"""
import getpass
import json
import subprocess
import sys
import urllib.error
import urllib.request

import keyring

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

SERVICE = "email-asistent"
GH = r"C:\Program Files\GitHub CLI\gh.exe"
REPO = "metropolitnidivadlo/email-asistent"


def api(tok, method, payload=None):
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/{method}", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"ok": False, "error_code": e.code, "description": e.read().decode(errors="replace")[:200]}


def ulozit():
    tok = getpass.getpass("Vložte token od BotFathera (nezobrazuje se) a stiskněte Enter: ").strip()
    if ":" not in tok:
        sys.exit("To nevypadá jako token (má tvar 123456789:AA...). Nic se neuložilo.")
    me = api(tok, "getMe")
    if not me.get("ok"):
        sys.exit(f"Telegram token odmítl ({me.get('error_code')}). Nic se neuložilo.")
    keyring.set_password(SERVICE, "TELEGRAM_BOT_TOKEN", tok)
    print(f"OK, bot @{me['result']['username']} uložen do Klíčenky.")
    print("Teď botovi v Telegramu napište zprávu (např. Ahoj). Pak dejte vědět v chatu.")


def put(name, value):
    r = subprocess.run([GH, "secret", "set", name, "--repo", REPO], input=value, text=True,
                       capture_output=True)
    print(("OK      " if r.returncode == 0 else "CHYBA   ") + name, r.stderr.strip() if r.returncode else "")


def dokoncit():
    tok = keyring.get_password(SERVICE, "TELEGRAM_BOT_TOKEN")
    if not tok:
        sys.exit("Token v Klíčence chybí – spusťte: python telegram_setup.py ulozit")
    me = api(tok, "getMe")
    print("Bot:", "@" + me["result"]["username"] if me.get("ok") else me)
    hook = api(tok, "getWebhookInfo").get("result", {}).get("url")
    if hook:
        print("Pozor: bot má nastavený webhook, getUpdates nefunguje.")
    upd = api(tok, "getUpdates")
    msgs = [u["message"] for u in upd.get("result", []) if "message" in u]
    print("Zpráv u bota:", len(msgs))
    if not msgs:
        sys.exit("Bot zatím nemá žádnou zprávu. Napište mu v Telegramu (tlačítko Start / Ahoj).")
    chat = msgs[-1]["chat"]
    keyring.set_password(SERVICE, "TELEGRAM_CHAT_ID", str(chat["id"]))
    print("Chat:", chat.get("first_name", ""), chat.get("type"))
    put("TELEGRAM_BOT_TOKEN", tok)
    put("TELEGRAM_CHAT_ID", str(chat["id"]))
    r = api(tok, "sendMessage", {"chat_id": chat["id"], "text": "✅ E-mailový asistent je napojený."})
    print("Zkušební zpráva:", "odeslána" if r.get("ok") else r)


if __name__ == "__main__":
    {"ulozit": ulozit, "dokoncit": dokoncit}.get(sys.argv[1] if len(sys.argv) > 1 else "", ulozit)()
