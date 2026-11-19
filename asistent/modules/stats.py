"""Ukázkový modul: zapisuje záznamy do data/log.jsonl (bez těla e-mailu)."""
import json
from datetime import datetime

from .. import config


def on_email(email, result):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "datum": email.date or datetime.now().isoformat(),
        "od": email.from_addr,
        "predmet": email.subject,
        "slozka": result["folder"],
        "needs_reply": result["needs_reply"],
        "important": result["important"],
        "summary": result["summary"],
        "koncept": bool(result.get("koncept")),
    }
    with open(config.DATA_DIR / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
