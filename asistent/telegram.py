"""Telegram Bot API (jen urllib). Bez tokenu vypíše do konzole.

Token se nikdy nevypisuje: chyby se hlásí jen typem výjimky (text může obsahovat URL s tokenem).
"""
import json
import urllib.request

try:  # lokálně na Windows: certifikáty ze systému (antivirus kontroluje HTTPS)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from .secrets import get_secret

MAX_TEXT = 4000   # limit Telegramu je 4096
MAX_KONCEPT = 3500


def _api(method, payload, timeout=20):
    """Zavolá metodu Bot API. Vrací pole 'result' (může být [] / True), nebo None při chybě."""
    token = get_secret("TELEGRAM_BOT_TOKEN")
    if not token:
        return None
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Telegram {method}: selhalo ({type(e).__name__})")
        return None
    if not data.get("ok"):
        print(f"Telegram {method}: odmítnuto")
        return None
    res = data.get("result")
    return True if res is None else res


def chat_id():
    return get_secret("TELEGRAM_CHAT_ID")


def send_summary(text):
    token, chat = get_secret("TELEGRAM_BOT_TOKEN"), chat_id()
    if not token or not chat:
        print("[Telegram nenastaven] Souhrn:\n" + text)
        return False
    if _api("sendMessage", {"chat_id": chat, "text": text[:MAX_TEXT]}) is None:
        print(text)
        return False
    return True


def keyboard_draft(draft_id):
    return [[{"text": "✅ Odeslat", "callback_data": f"send:{draft_id}"},
             {"text": "🗑 Zahodit", "callback_data": f"drop:{draft_id}"}]]


def card_text(od, predmet, shrnuti, body):
    """Text karty konceptu (max ~4000 znaků, text konceptu zkrácen na 3500)."""
    body = body or ""
    if len(body) > MAX_KONCEPT:
        body = body[:MAX_KONCEPT] + "\n[...zkráceno]"
    head = f"Koncept odpovědi\nOd: {od}\nPředmět: {predmet}\n"
    if shrnuti:
        head += f"Shrnutí: {shrnuti}\n"
    if "[DOPLNIT" in body:
        head += "⚠ Koncept obsahuje [DOPLNIT] - před odesláním ho doplňte v Outlooku.\n"
    text = head + "\n" + body
    return text[:MAX_TEXT]


def send_draft_card(draft_id, od, predmet, shrnuti, body):
    """Pošle kartu konceptu s tlačítky Odeslat / Zahodit. Vrací True/False."""
    chat = chat_id()
    if not get_secret("TELEGRAM_BOT_TOKEN") or not chat:
        print(f"[Telegram nenastaven] Koncept {draft_id}:\n" + card_text(od, predmet, shrnuti, body))
        return False
    return _api("sendMessage", {"chat_id": chat, "text": card_text(od, predmet, shrnuti, body),
                                "reply_markup": {"inline_keyboard": keyboard_draft(draft_id)}}) is not None


def answer_callback(callback_id, text=""):
    return _api("answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:190]}) is not None


def edit_message(chat, message_id, text, buttons=None):
    """Upraví text zprávy; buttons=None odstraní klávesnici."""
    return _api("editMessageText", {"chat_id": chat, "message_id": message_id, "text": text[:MAX_TEXT],
                                    "reply_markup": {"inline_keyboard": buttons or []}}) is not None


def get_updates(offset=None, limit=100):
    """Čekající updates (callback_query a zprávy). offset=N potvrdí všechny s update_id < N. None = chyba."""
    payload = {"limit": limit, "timeout": 0, "allowed_updates": ["callback_query", "message"]}
    if offset is not None:
        payload["offset"] = offset
    res = _api("getUpdates", payload)
    return res if isinstance(res, list) else None
