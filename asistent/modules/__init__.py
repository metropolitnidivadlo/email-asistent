"""Jednoduchý registr modulů.

Modul je objekt/modul s volitelnými funkcemi:
  on_email(email, result)   - po zpracování každé zprávy (result je slovník)
  on_run_end(results)       - na konci běhu (results je seznam slovníků)
Nový sektor (finance, vstupenky) = nový soubor + řádek v load_default().
"""
import sys

_modules = []


def register(module):
    if module not in _modules:
        _modules.append(module)


def load_default():
    from . import stats
    register(stats)


def _call(name, *args):
    for m in _modules:
        fn = getattr(m, name, None)
        if fn:
            try:
                fn(*args)
            except Exception as e:  # chyba modulu nesmí zastavit zpracování pošty
                print(f"  [modul {getattr(m, '__name__', m)}] {name} selhal: {type(e).__name__}",
                      file=sys.stderr)


def on_email(email, result):
    _call("on_email", email, result)


def on_run_end(results):
    _call("on_run_end", results)
