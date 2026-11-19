"""Souhrn do Telegramu přes Bot API (jen urllib). Bez tokenu vypíše do konzole."""
import json
import urllib.request

try:  # lokálně na Windows: certifikáty ze systému (antivirus kontroluje HTTPS)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from .secrets import get_secret


def send_summary(text):
    token, chat = get_secret("TELEGRAM_BOT_TOKEN"), get_secret("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[Telegram nenastaven] Souhrn:\n" + text)
        return False
    payload = json.dumps({"chat_id": chat, "text": text[:4000]}).encode("utf-8")
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                 data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status == 200
    except Exception as e:  # text chyby může obsahovat URL s tokenem, proto jen typ
        print(f"Telegram: odeslání selhalo ({type(e).__name__})")
        print(text)
        return False
