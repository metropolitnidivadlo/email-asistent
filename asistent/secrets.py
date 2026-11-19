"""Načítání tajných údajů: nejdřív proměnné prostředí (GitHub Secrets), pak Klíčenka.

Hesla se nikdy nelogují ani nevypisují.
"""
import os

# Stejné jako v imap_core.py (existující uložení v Klíčence Windows)
IMAP_SERVICE = "email-asistent-wedos"
OSTATNI_SERVICE = "email-asistent"


def _keyring():
    """Vrátí modul keyring, nebo None (např. na Linuxu v GitHub Actions bez backendu)."""
    try:
        import keyring  # noqa: WPS433
        return keyring
    except Exception:
        return None


def _kr_get(service, username):
    kr = _keyring()
    if kr is None:
        return None
    try:
        return kr.get_password(service, username)
    except Exception:
        return None  # chybějící backend apod. nesmí shodit běh


def get_secret(name):
    """Vrátí hodnotu tajného údaje, nebo None, pokud chybí."""
    val = os.environ.get(name)
    if val:
        return val
    if name == "IMAP_USER":
        return _kr_get(IMAP_SERVICE, "__user__")
    if name == "IMAP_PASSWORD":
        user = get_secret("IMAP_USER")
        return _kr_get(IMAP_SERVICE, user) if user else None
    return _kr_get(OSTATNI_SERVICE, name)
