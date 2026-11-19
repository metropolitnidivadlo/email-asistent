"""AI přes Claude Code CLI (předplatné, bez API klíče).

Volá `claude -p --output-format json --model <model>` s promptem na stdin.
Autentizace je věcí CLI (v GitHub Actions env CLAUDE_CODE_OAUTH_TOKEN). Kód s tokenem nepracuje.
Selže-li cokoli nebo CLI chybí, vrací None a volající použije fallback.
"""
import json
import shutil
import subprocess
import sys

from . import config

TIMEOUT = 120


def _cli():
    return shutil.which("claude") or shutil.which("claude.cmd")


def available():
    return _cli() is not None


def ask_text(prompt, system=None):
    cli = _cli()
    if not cli:
        return None
    full = f"{system}\n\n---\n\n{prompt}" if system else prompt
    try:
        p = subprocess.run([cli, "-p", "--output-format", "json", "--model", config.MODEL],
                           input=full, capture_output=True, text=True, encoding="utf-8",
                           timeout=TIMEOUT)
        if p.returncode != 0:
            print(f"  [AI] claude CLI skončilo s kódem {p.returncode}", file=sys.stderr)
            return None
        data = json.loads(p.stdout)
        if data.get("is_error"):
            print("  [AI] claude CLI vrátilo chybu", file=sys.stderr)
            return None
        res = data.get("result")
        return res.strip() if isinstance(res, str) and res.strip() else None
    except Exception as e:
        print(f"  [AI] volání claude CLI selhalo: {type(e).__name__}", file=sys.stderr)
        return None


def extract_json(text):
    """Vytáhne první JSON objekt z textu (i v ```json blocích)."""
    if not text:
        return None
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        obj = json.loads(text[a:b + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def ask_json(prompt, system=None):
    return extract_json(ask_text(prompt, system))
