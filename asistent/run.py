"""Příkazová řádka e-mailového asistenta. Nikdy neodesílá e-maily."""
import argparse
import json
import os
import sys

from . import ai, classify, config, drafts, modules, style, telegram
from .imap_client import Mailbox
from .secrets import get_secret


def _md_cell(s):
    return str(s or "").replace("|", "/").replace("\n", " ").strip()


def cmd_zkouska(args):
    """Nanečisto: nic se neposouvá, neoznačuje ani nevkládá do schránky."""
    mb = Mailbox().connect()
    try:
        emails = mb.fetch_latest("INBOX", args.pocet)
        st = style.get_style(mb)
    finally:
        mb.logout()
    ai_ok = "ano" if ai.available() else "ne (claude CLI nenalezeno)"
    rows = []
    for em in emails:
        r = classify.classify(em)
        koncept = None
        if r.needs_reply and r.folder != config.FOLDER_NEWSLETTER:
            koncept = drafts.draft_text(em, st)
        rows.append({"datum": em.date, "od": f"{em.from_name} <{em.from_addr}>".strip(),
                     "predmet": em.subject, **r.as_dict(), "koncept": koncept})
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    vstup = []
    for em in emails:  # vstup pro dokončení AI části mimo skript
        pr = classify.rule_based(em)
        vstup.append({"uid": em.uid, "od": f"{em.from_name} <{em.from_addr}>".strip(),
                      "datum": em.date, "predmet": em.subject, "text": em.text[:3000],
                      "hlavicky": {"List-Unsubscribe": em.list_unsubscribe, "Precedence": em.precedence,
                                   "Auto-Submitted": em.auto_submitted},
                      "pravidla": pr.as_dict() if pr else None})
    (config.DATA_DIR / "zkouska_vstup.json").write_text(
        json.dumps(vstup, ensure_ascii=False, indent=2), encoding="utf-8")
    (config.DATA_DIR / "zkouska.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [f"# Zkouška (nanečisto) - {len(rows)} zpráv", "", f"AI k dispozici: {ai_ok}", "",
          "| Datum | Od | Předmět | Navržená složka | Důležité | Potřeba odpovědi | Shrnutí |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append("| " + " | ".join([
            _md_cell(r["datum"][:16]), _md_cell(r["od"]), _md_cell(r["predmet"]), _md_cell(r["folder"]),
            "ano" if r["important"] else "ne", "ano" if r["needs_reply"] else "ne",
            _md_cell(r["summary"])]) + " |")
    md += ["", "## Navržené koncepty", ""]
    any_k = False
    for r in rows:
        if r["koncept"]:
            any_k = True
            md += [f"### Re: {r['predmet']}  (komu: {r['od']})", "", r["koncept"], "", "---", ""]
    if not any_k:
        md.append("(žádné koncepty)")
    (config.DATA_DIR / "zkouska.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Hotovo: {len(rows)} zpráv. Výsledek: {config.DATA_DIR / 'zkouska.md'}")
    print("Ve schránce se nic nezměnilo.")


def cmd_ostre(args):
    if os.environ.get("ASISTENT_OSTRE") != "1":
        sys.exit("Ostrý běh odmítnut: nastavte ASISTENT_OSTRE=1.")
    if not args.ignoruj_cas and not config.in_time_window():
        print(f"Mimo časové okno {config.WINDOW_START}-{config.WINDOW_END} h ({config.TZ_NAME}); končím.")
        return
    modules.load_default()
    mb = Mailbox().connect()
    results, st, chyby = [], None, 0
    try:
        zbyva = mb.ensure_folders(list(config.FOLDERS) + [config.FOLDER_DRAFTS], create=True)
        if zbyva:
            print(f"Nepodařilo se vytvořit složky: {', '.join(zbyva)}")
        emails = mb.fetch_unprocessed("INBOX")
        print(f"Ke zpracování: {len(emails)} zpráv.")
        for em in emails:
            try:
                r = classify.classify(em).as_dict()
                r["koncept"] = False
                if r["needs_reply"] and r["folder"] != config.FOLDER_NEWSLETTER:
                    if st is None:
                        st = style.get_style(mb)
                        mb._select("INBOX", readonly=False)  # styl mohl přepnout složku
                    body = drafts.draft_text(em, st)
                    if body:
                        msg = drafts.build_message(em, body, mb.user)
                        r["koncept"] = mb.append_draft(config.FOLDER_DRAFTS, msg)
                        mb._select("INBOX", readonly=False)
                mb.add_flag(em.uid, config.DONE_KEYWORD)
                mb.move(em.uid, r["folder"])
                modules.on_email(em, r)
                results.append({"predmet": em.subject, "od": em.from_addr, **r})
            except Exception as e:
                chyby += 1
                print(f"  Zpráva UID {em.uid} selhala: {type(e).__name__}", file=sys.stderr)
    finally:
        mb.logout()
    modules.on_run_end(results)
    if not results and not chyby:
        print("Nic nového.")
        return
    dulezite = [r for r in results if r["important"]]
    koncepty = sum(1 for r in results if r["koncept"])
    lines = [f"E-mailový asistent: přišlo {len(results)} zpráv, důležitých {len(dulezite)}, "
             f"konceptů čeká {koncepty}."]
    for r in dulezite:
        lines.append(f"! {r['od']}: {r['predmet']} - {r['summary']}")
    if chyby:
        lines.append(f"Chyby při zpracování: {chyby}")
    telegram.send_summary("\n".join(lines))


def cmd_styl(args):
    if not ai.available():
        sys.exit("Bez claude CLI nelze profil stylu vygenerovat (použije se výchozí formální styl).")
    mb = Mailbox().connect()
    try:
        text = style.get_style(mb, refresh=True)
    finally:
        mb.logout()
    print(f"Profil stylu uložen do {style.STYL_SOUBOR}:\n\n{text}")


def cmd_vzorky(args):
    """Texty z odeslané pošty (bez citací) do data/styl_vzorky.json, bez AI."""
    mb = Mailbox().connect()
    try:
        vzorky = mb.fetch_sent_samples(args.pocet)
    finally:
        mb.logout()
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "styl_vzorky.json").write_text(
        json.dumps(vzorky, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Uloženo {len(vzorky)} vzorků do {config.DATA_DIR / 'styl_vzorky.json'}")


def cmd_slozky(args):
    mb = Mailbox().connect()
    try:
        potreba = list(config.FOLDERS) + [config.FOLDER_DRAFTS]
        for f in potreba:
            real = mb.resolve(f)
            print(f"  {'OK     ' if real else 'CHYBÍ  '} {f}" + (f"  ({real})" if real and real != f else ""))
        chybi = [f for f in potreba if mb.resolve(f) is None]
        if chybi and args.vytvor:
            zbyva = mb.ensure_folders(chybi, create=True)
            print("Vytvořeno." if not zbyva else f"Nevytvořeno: {', '.join(zbyva)}")
        elif chybi:
            print("Pro vytvoření chybějících složek přidejte --vytvor.")
    finally:
        mb.logout()


def cmd_kokpit(args):
    """HTML kokpit; ze schránky jen čte (readonly), nic nemění."""
    from pathlib import Path
    from . import kokpit, kokpit_data
    if args.z_zkousky:
        data = kokpit_data.from_zkouska(config.DATA_DIR / "zkouska_ai.json")
    else:
        mb = Mailbox().connect()
        try:
            data = kokpit_data.collect(mb)
        finally:
            mb.logout()
    out = Path(args.vystup)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(kokpit.render(data), encoding="utf-8")
    print(f"Kokpit uložen do {out}")


def build_parser():
    p = argparse.ArgumentParser(prog="run.py", description="E-mailový asistent Metropolitního divadla "
                                "(nikdy neodesílá e-maily, jen třídí a ukládá koncepty).")
    sub = p.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("zkouska", help="nanečisto: nic se ve schránce nemění")
    z.add_argument("--pocet", type=int, default=10, help="kolik posledních zpráv z INBOX (výchozí 10)")
    z.set_defaults(fn=cmd_zkouska)
    o = sub.add_parser("ostre", help="ostrý běh (vyžaduje ASISTENT_OSTRE=1)")
    o.add_argument("--ignoruj-cas", action="store_true", help="ignorovat časové okno 7-22 h")
    o.set_defaults(fn=cmd_ostre)
    s = sub.add_parser("styl", help="vygeneruje profil stylu z odeslané pošty")
    s.add_argument("--obnovit-styl", action="store_true", help="(styl se tímto příkazem vždy přegeneruje)")
    s.set_defaults(fn=cmd_styl)
    v = sub.add_parser("vzorky-stylu", help="uloží texty z odeslané pošty (bez AI)")
    v.add_argument("--pocet", type=int, default=30)
    v.set_defaults(fn=cmd_vzorky)
    f = sub.add_parser("slozky", help="vypíše stav složek")
    f.add_argument("--vytvor", action="store_true", help="vytvoří chybějící složky")
    f.set_defaults(fn=cmd_slozky)
    k = sub.add_parser("kokpit", help="vygeneruje HTML kokpit (jen čtení ze schránky)")
    k.add_argument("--z-zkousky", action="store_true", help="data z data/zkouska_ai.json, bez připojení")
    k.add_argument("--vystup", default="site/index.html", help="výstupní soubor (výchozí site/index.html)")
    k.set_defaults(fn=cmd_kokpit)
    return p


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()

