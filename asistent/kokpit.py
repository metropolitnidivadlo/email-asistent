"""Vykreslení kokpitu do jednoho samostatného HTML (inline CSS, bez JS; jediný externí zdroj je písmo Karla z Google Fonts)."""
import re
import unicodedata
from collections import Counter
from datetime import datetime
from html import escape as _esc
from urllib.parse import quote

from . import config

# Barvy; test v tests/test_kokpit.py z nich počítá kontrast podle WCAG 2.1.
# page = pozadí stránky, card = karty, bg/box = starší názvy (stejné role), bar = horní lišta,
# accent/accent_fg = plocha tlačítka a pruhů (#D5291F / #F64A41 s tmavým textem).
PALETTES = {
    "light": {"bg": "#FFFFFF", "fg": "#171717", "muted": "#4B4B4B", "box": "#F7F5F3", "border": "#8A8A8A",
              "rule": "#8A8A8A", "head": "#D5291F", "th": "#E9E6E3", "badge_bg": "#B3201A",
              "badge_fg": "#FFFFFF", "page": "#F7F5F3", "card": "#FFFFFF", "line": "#D9D5D1",
              "accent": "#D5291F", "accent_fg": "#FFFFFF", "bar": "#171717", "bar_fg": "#FFFFFF",
              "bar_muted": "#C9C9C9", "bar_accent": "#FF6B62"},
    "dark": {"bg": "#0D0D0D", "fg": "#F2F2F2", "muted": "#B8B8B8", "box": "#171717", "border": "#767676",
             "rule": "#767676", "head": "#FF6B62", "th": "#262626", "badge_bg": "#FF6B62",
             "badge_fg": "#0D0D0D", "page": "#0D0D0D", "card": "#171717", "line": "#2E2E2E",
             "accent": "#F64A41", "accent_fg": "#0D0D0D", "bar": "#000000", "bar_fg": "#F2F2F2",
             "bar_muted": "#B8B8B8", "bar_accent": "#FF6B62"},
}
# (popředí, pozadí, minimální poměr): text >= 4.5, okraje, pruhy a ikonky >= 3
PAIRS = [
    ("fg", "bg", 4.5), ("fg", "box", 4.5), ("muted", "bg", 4.5), ("muted", "box", 4.5),
    ("head", "box", 4.5), ("head", "bg", 4.5), ("fg", "th", 4.5), ("muted", "th", 4.5),
    ("badge_fg", "badge_bg", 4.5), ("border", "bg", 3), ("border", "box", 3), ("rule", "box", 3),
    ("badge_bg", "box", 3),
    ("fg", "page", 4.5), ("fg", "card", 4.5), ("muted", "page", 4.5), ("muted", "card", 4.5),
    ("head", "page", 4.5), ("head", "card", 4.5), ("border", "page", 3), ("border", "card", 3),
    ("badge_bg", "card", 3), ("badge_bg", "page", 3),
    ("accent_fg", "accent", 4.5), ("accent", "card", 3), ("accent", "page", 3), ("accent", "th", 3),
    ("accent", "bar", 3), ("bar_fg", "bar", 4.5), ("bar_muted", "bar", 4.5), ("bar_accent", "bar", 4.5),
]


def _vars(p):
    return "".join(f"--{k}:{v};" for k, v in p.items())


CSS = (
    ":root{" + _vars(PALETTES["light"]) + "color-scheme:light dark}"
    "@media (prefers-color-scheme:dark){:root{" + _vars(PALETTES["dark"]) + "}}"
    "*{box-sizing:border-box}"
    "html{-webkit-text-size-adjust:100%}"
    "@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}"
    "body{margin:0;background:var(--page);color:var(--fg);"
    "font:1rem/1.5 'Karla',system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;overflow-wrap:anywhere}"
    "a{color:var(--head)}"
    ":focus-visible{outline:3px solid var(--head);outline-offset:2px}"
    # horní lišta
    ".bar{position:sticky;top:0;z-index:10;background:var(--bar);color:var(--bar_fg);"
    "border-bottom:4px solid var(--accent)}"
    ".bar-in{max-width:90rem;margin:0 auto;padding:.6rem 1rem;display:flex;flex-wrap:wrap;gap:.5rem 1.25rem;"
    "align-items:center;justify-content:space-between}"
    ".bar h1{margin:0;font-size:1.05rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;"
    "color:var(--bar_fg)}"
    ".bar h1 span{color:var(--bar_accent)}"
    ".bar-r{display:flex;flex-wrap:wrap;gap:.4rem 1rem;align-items:center}"
    ".gen{margin:0;color:var(--bar_muted);font-size:.9rem}"
    ".bar :focus-visible{outline-color:var(--bar_accent)}"
    ".btn{display:inline-block;padding:.5rem 1rem;background:var(--accent);color:var(--accent_fg);"
    "border:2px solid var(--accent);border-radius:0;font-weight:700;text-decoration:none;"
    "text-transform:uppercase;letter-spacing:.08em;font-size:.9rem}"
    ".btn:hover{text-decoration:underline}"
    # rozvržení
    "main{max-width:90rem;margin:0 auto;padding:1rem}"
    ".kpi{list-style:none;margin:0 0 1rem;padding:0;display:grid;gap:.75rem;grid-template-columns:repeat(2,minmax(0,1fr))}"
    ".kpi li{background:var(--card);border:1px solid var(--line);border-top:4px solid var(--accent);"
    "padding:.75rem 1rem;box-shadow:0 1px 3px rgba(0,0,0,.12)}"
    ".kpi-v{display:block;font-size:2.2rem;line-height:1.1;font-weight:700;color:var(--fg)}"
    ".kpi-l{display:block;margin-top:.25rem;color:var(--muted);font-size:.85rem;font-weight:600;"
    "text-transform:uppercase;letter-spacing:.06em}"
    ".grid{display:grid;gap:1rem;grid-template-columns:minmax(0,1fr)}"
    ".col{display:grid;gap:1rem;align-content:start;min-width:0}"
    "@media (min-width:640px){.kpi{grid-template-columns:repeat(3,minmax(0,1fr))}}"
    "@media (min-width:1000px){.kpi{grid-template-columns:repeat(5,minmax(0,1fr))}"
    ".grid{grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:1.25rem}.col{gap:1.25rem}"
    ".bar-in,main{padding-left:1.5rem;padding-right:1.5rem}}"
    # karty
    "section{background:var(--card);border:1px solid var(--line);box-shadow:0 1px 3px rgba(0,0,0,.12);"
    "padding:1rem;margin:0;min-width:0}"
    "section.hlavni{border-top:6px solid var(--accent);padding:1.25rem}"
    "section.siroka{margin-top:1.25rem}"
    "section>h2{font-size:1.2rem;margin:0 0 .75rem;padding-left:.6rem;border-left:5px solid var(--accent);"
    "text-transform:uppercase;letter-spacing:.08em;line-height:1.2;color:var(--fg)}"
    "section.hlavni>h2{font-size:1.6rem}"
    "h3{font-size:1rem;margin:1rem 0 .5rem;text-transform:uppercase;letter-spacing:.06em;color:var(--head)}"
    ".napoveda{margin:0 0 1rem;padding:.6rem .8rem;background:var(--page);border-left:4px solid var(--accent);"
    "font-weight:500}"
    "p{margin:.25rem 0 .75rem}"
    ".muted{color:var(--muted)}"
    # koncepty
    ".koncepty{display:grid;gap:.75rem;grid-template-columns:minmax(0,1fr)}"
    ".koncept{background:var(--page);border:1px solid var(--line);border-left:5px solid var(--accent);padding:.75rem 1rem;"
    "min-width:0}"
    ".koncept h3{margin:.25rem 0 .25rem;font-size:1.1rem;text-transform:none;letter-spacing:0;color:var(--fg)}"
    ".koncept .meta{margin:0 0 .5rem;color:var(--muted);font-size:.9rem}"
    ".nahled{margin:0;white-space:pre-line;font-size:.95rem;border-top:1px solid var(--line);padding-top:.5rem}"
    # štítky
    ".st{display:inline-block;padding:0 .45rem;margin-right:.35rem;border:1px solid transparent;border-radius:0;"
    "font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;line-height:1.5}"
    ".st-high{background:var(--badge_bg);color:var(--badge_fg)}"
    ".st-late{background:var(--fg);color:var(--card)}"
    ".st-contact{border-color:var(--fg);color:var(--fg)}"
    ".st-new{border-color:var(--border);color:var(--muted)}"
    # úkoly
    ".ukoly{list-style:none;margin:0 0 .75rem;padding:0}"
    ".ukoly li{padding:.5rem 0;border-bottom:1px solid var(--line)}"
    ".ukoly li:last-child{border-bottom:0}"
    # tabulky
    ".tw{overflow-x:auto;margin:0 0 1rem}"
    "table{border-collapse:collapse;width:100%;font-size:.9rem}"
    "caption{text-align:left;font-weight:700;padding:.25rem 0;text-transform:uppercase;letter-spacing:.05em;"
    "font-size:.85rem}"
    "th,td{border:1px solid var(--line);padding:.35rem .5rem;text-align:left;vertical-align:top}"
    "thead th{background:var(--th);color:var(--fg)}"
    "tbody th{font-weight:600}"
    "td.n,th.n{text-align:right}"
    ".nowrap{white-space:nowrap}"
    "details{border:1px solid var(--line);margin:0 0 .5rem;padding:.25rem .6rem;background:var(--card)}"
    "summary{cursor:pointer;font-weight:700;padding:.35rem 0}"
    "details[open]>summary{margin-bottom:.35rem}"
    # pruhové grafy
    ".bars{list-style:none;margin:0 0 1rem;padding:0;display:grid;gap:.4rem}"
    ".bars li{display:grid;grid-template-columns:minmax(5rem,38%) minmax(0,1fr) 2.6rem;gap:.5rem;align-items:center;"
    "font-size:.9rem}"
    ".b-l{min-width:0}"
    ".b-t{display:block;height:.9rem;background:var(--th)}"
    ".b-f{display:block;height:100%;background:var(--accent)}"
    ".b-v{text-align:right;font-weight:700}"
    ".prehled{display:grid;gap:.5rem;grid-template-columns:repeat(3,minmax(0,1fr));margin:0 0 .75rem}"
    ".prehled p{margin:0;padding:.5rem;background:var(--page);border:1px solid var(--line)}"
    ".prehled strong{display:block;font-size:1.6rem;line-height:1.1}"
    "@media (max-width:480px){.bar-in,main{padding-left:16px;padding-right:16px}"
    "section{padding:.75rem}section.hlavni{padding:.9rem .75rem}table{font-size:.8rem}"
    "th,td{padding:.25rem .3rem}.kpi-v{font-size:1.8rem}.bar h1{font-size:.9rem}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}"
)

POSTA_ZBYTEK = ("INBOX", "Ostatní", "Newslettery")
DOPRAVA = ("Představení a zájezdy", "Doprava", "Nabídky a objednávky")
FINANCE = "Faktury a finance"
NABIDKY = "Nabídky a objednávky"
PREVIEW_CHARS = 400
KONCEPTY_VIDITELNE = 6


def e(x):
    return _esc(str(x if x is not None else ""), quote=True)


def _fmt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d. %m. %H:%M")
    except Exception:
        return str(iso)[:16]


def _fmt_full(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d. %m. %Y %H:%M")
    except Exception:
        return str(iso)


def _name(folder):
    return "Doručená pošta (INBOX)" if folder == "INBOX" else folder


def _tw(table):
    return f"<div class=\"tw\">{table}</div>"


def _msg_table(items, caption, with_folder=False):
    if not items:
        return f"<p class=\"muted\">{e(caption)}: žádné zprávy.</p>"
    head = "<th scope=\"col\">Datum</th><th scope=\"col\">Od</th><th scope=\"col\">Předmět</th>"
    if with_folder:
        head += "<th scope=\"col\">Složka</th>"
    rows = []
    for it in items:
        cells = (f"<th scope=\"row\" class=\"nowrap\">{e(_fmt(it['date']))}</th><td>{e(it['from'])}</td>"
                 f"<td>{e(it['subject'])}</td>")
        if with_folder:
            cells += f"<td>{e(it.get('folder', ''))}</td>"
        rows.append(f"<tr>{cells}</tr>")
    return _tw(f"<table><caption>{e(caption)}</caption><thead><tr>{head}</tr></thead>"
               f"<tbody>{''.join(rows)}</tbody></table>")


def _counts_table(folders, names, caption="Počty zpráv"):
    rows = []
    for n in names:
        f = folders.get(n)
        if f is None:
            continue
        rows.append(f"<tr><th scope=\"row\">{e(_name(n))}</th><td class=\"n\">{f['today']}</td>"
                    f"<td class=\"n\">{f['week']}</td><td class=\"n\">{f['month']}</td></tr>")
    if not rows:
        return ""
    return _tw(f"<table><caption>{e(caption)}</caption><thead><tr><th scope=\"col\">Složka</th>"
               "<th scope=\"col\" class=\"n\">Dnes</th><th scope=\"col\" class=\"n\">7 dní</th>"
               f"<th scope=\"col\" class=\"n\">30 dní</th></tr></thead><tbody>{''.join(rows)}</tbody></table>")


def _bars(rows, caption):
    """Pruhový graf z divů; hodnota je vždy i číslem vedle pruhu. rows = [(popisek, podpopisek, hodnota)]."""
    if not rows:
        return ""
    mx = max((v for _, _, v in rows), default=0) or 1
    lis = []
    for label, sub, v in rows:
        w = 0 if not v else max(2, round(100 * v / mx))
        sub_html = f"<br><span class=\"muted\">{e(sub)}</span>" if sub else ""
        lis.append(f"<li><span class=\"b-l\">{e(label)}{sub_html}</span>"
                   f"<span class=\"b-t\" aria-hidden=\"true\"><span class=\"b-f\" style=\"width:{w}%\"></span></span>"
                   f"<span class=\"b-v\">{e(v)}</span></li>")
    return f"<h3>{e(caption)}</h3><ul class=\"bars\">{''.join(lis)}</ul>"


def _section(sid, title, body, cls=""):
    c = f" class=\"{cls}\"" if cls else ""
    return f"<section{c} aria-labelledby=\"{sid}\"><h2 id=\"{sid}\">{e(title)}</h2>{body}</section>"


def _today(d):
    try:
        return datetime.fromisoformat(d.get("generated")).date()
    except Exception:
        return config.now_prague().date()


def _preview(text):
    t = re.sub(r"[ \t]+", " ", str(text or "")).strip()
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    if len(t) > PREVIEW_CHARS:
        t = t[:PREVIEW_CHARS].rstrip() + "…"
    return t


def _koncept_card(i):
    prio = "<span class=\"st st-high\">Důležité</span>" if i.get("important") else ""
    prev = _preview(i.get("preview"))
    nahled = (f"<p class=\"nahled\">{e(prev)}</p>" if prev
              else "<p class=\"nahled muted\">Náhled textu není k dispozici.</p>")
    return (f"<article class=\"koncept\">{prio}<h3>{e(i.get('subject') or '(bez předmětu)')}</h3>"
            f"<p class=\"meta\">Komu: <strong>{e(i.get('to'))}</strong> · <time>{e(_fmt(i['date']))}</time></p>"
            f"{nahled}</article>")


def _sec_koncepty(d):
    dr = d.get("drafts", {"count": 0, "items": []})
    body = ("<p class=\"napoveda\">Schvalte v Telegramu tlačítkem ✅ Odeslat, nebo upravte ve složce "
            "Koncepty v Outlooku.</p>")
    items = dr.get("items") or []
    if not items:
        body += "<p class=\"muted\">Žádné koncepty nečekají.</p>"
    else:
        cards = [_koncept_card(i) for i in items]
        body += f"<div class=\"koncepty\">{''.join(cards[:KONCEPTY_VIDITELNE])}</div>"
        if len(cards) > KONCEPTY_VIDITELNE:
            body += (f"<details><summary>Další koncepty ({len(cards) - KONCEPTY_VIDITELNE})</summary>"
                     f"<div class=\"koncepty\">{''.join(cards[KONCEPTY_VIDITELNE:])}</div></details>")
        if dr.get("count", 0) > len(items):
            body += f"<p class=\"muted\">Zobrazeno {len(items)} z {e(dr['count'])} konceptů.</p>"
    return _section("koncepty", "Koncepty k odeslání", body, "hlavni")


def _sec_dnes(d):
    imp = d.get("important_today", [])
    if imp:
        rows = "".join(
            f"<tr><th scope=\"row\" class=\"nowrap\">{e(_fmt(i['date']))}</th><td>{e(i['from'])}</td>"
            f"<td><span class=\"st st-high\">Důležité</span>{e(i['subject'])}"
            + (f"<br><span class=\"muted\">{e(i['summary'])}</span>" if i.get("summary") else "")
            + f"</td><td>{e(i.get('folder', ''))}</td></tr>" for i in imp)
        body = _tw("<table><caption>Důležité zprávy dnes</caption><thead><tr><th scope=\"col\">Čas</th>"
                   "<th scope=\"col\">Od</th><th scope=\"col\">Předmět</th><th scope=\"col\">Složka</th>"
                   f"</tr></thead><tbody>{rows}</tbody></table>")
    else:
        body = "<p class=\"muted\">Dnes nic důležitého.</p>"
    return _section("dnes", "Důležité dnes", body)


def _sec_ukoly(d):
    """Úkoly a připomínky; vysoká priorita zvýrazněná textem i barvou, prošlé termíny 'po termínu'."""
    uk = d.get("ukoly") or {}
    items = uk.get("ukoly") or []
    if not items:
        return _section("ukoly", "Úkoly a připomínky", "<p class=\"muted\">Zatím žádné úkoly.</p>")
    today = _today(d).isoformat()
    order = {"vysoká": 0, "střední": 1, "nízká": 2}
    items = sorted(items, key=lambda u: (order.get(u.get("priorita"), 9), u.get("termin") or "9999-99-99"))
    lis = []
    for u in items:
        prio = u.get("priorita")
        badge = "<span class=\"st st-high\">Vysoká priorita</span>" if prio == "vysoká" else (
            f"<span class=\"muted\">({e(prio)})</span> " if prio else "")
        txt = f"<strong>{e(u.get('text'))}</strong>" if prio == "vysoká" else e(u.get("text"))
        extra = ""
        t = u.get("termin")
        if t:
            if str(t) < today:
                extra += f" <span class=\"st st-late\">po termínu</span> termín {e(t)}"
            else:
                extra += f" <span class=\"muted\">termín {e(t)}</span>"
        if u.get("zdroj"):
            extra += f" <span class=\"muted\">[{e(u['zdroj'])}]</span>"
        lis.append(f"<li>{badge}{txt}{extra}</li>")
    note = f"<p class=\"muted\">{e(uk['poznamka'])}</p>" if uk.get("poznamka") else ""
    created = (f"<p class=\"muted\">Vytvořeno: {e(_fmt_full(uk['vytvoreno']))}</p>"
               if uk.get("vytvoreno") else "")
    return _section("ukoly", "Úkoly a připomínky", f"<ul class=\"ukoly\">{''.join(lis)}</ul>{note}{created}")


def _latest_details(items, summary, open_=False):
    if not items:
        return f"<p class=\"muted\">{e(summary)}: žádné zprávy.</p>"
    return (f"<details{' open' if open_ else ''}><summary>{e(summary)}</summary>"
            f"{_msg_table(items, summary)}</details>")


def _sec_posta(d):
    f = d.get("folders", {})
    body = _counts_table(f, ["INBOX"] + [n for n in config.FOLDERS])
    for n in POSTA_ZBYTEK:
        if n in f:
            body += _latest_details(f[n]["latest"], f"{_name(n)} - posledních {len(f[n]['latest'])} zpráv",
                                    n == "INBOX")
    return _section("posta", "Pošta podle složek", body)


def _sec_predstaveni(d):
    f = d.get("folders", {})
    body = _counts_table(f, DOPRAVA)
    for n in DOPRAVA:
        if n in f:
            body += _latest_details(f[n]["latest"], f"{n} - posledních {len(f[n]['latest'])} zpráv")
    return _section("predstaveni", "Představení a doprava", body)


def _sender_bars(items, caption):
    if not items:
        return f"<h3>{e(caption)}</h3><p class=\"muted\">Žádná data.</p>"
    rows = [((i["name"] or i["addr"]), (i["addr"] if i["name"] else ""), i["count"]) for i in items]
    return _bars(rows, caption)


def _sec_stat(d):
    f = d.get("folders", {})
    inbox = f.get("INBOX", {"week": 0, "month": 0})
    body = (f"<p>Za posledních 7 dní: <strong>{e(inbox['week'])}</strong> zpráv, "
            f"za 30 dní: <strong>{e(inbox['month'])}</strong> zpráv (INBOX).</p>")
    r = d.get("reply", {})
    if r.get("avg_hours") is not None:
        body += (f"<p>Průměrná doba odpovědi (30 dní): <strong>{e(r['avg_hours']).replace('.', ',')} h</strong> "
                 f"({e(r.get('count', 0))} spárovaných odpovědí).</p>")
    else:
        body += "<p class=\"muted\">Průměrná doba odpovědi: nedostatek dat.</p>"
    body += _bars([(_name(n), "", f[n]["month"]) for n in ["INBOX"] + list(config.FOLDERS) if n in f],
                  "Zprávy podle složek (30 dní)")
    ts = d.get("top_senders", {})
    body += _sender_bars(ts.get("week", []), "Nejčastější odesílatelé - týden (top 5)")
    body += _sender_bars(ts.get("month", []), "Nejčastější odesílatelé - měsíc (top 5)")
    if FINANCE in f:
        body += "<h3>Faktury a finance</h3>"
        body += _counts_table(f, [FINANCE], "Faktury a finance - počty")
        body += _latest_details(f[FINANCE]["latest"], f"{FINANCE} - posledních {len(f[FINANCE]['latest'])} zpráv")
    return _section("statistiky", "Statistiky a finance", body)


TYPY = {"divadlo": "divadlo", "kulturni_dum": "kulturní dům", "kulturni_centrum": "kulturní centrum",
        "festival": "festival"}
_EMAIL_RE = re.compile(r"^[^\s@<>\"']+@[^\s@<>\"']+\.[^\s@<>\"']+$")


def _typ(t):
    return TYPY.get((t or "").strip().lower(), "jiné")


def _link_web(url):
    url = (url or "").strip()
    if not url:
        return ""
    if re.match(r"^https?://", url, re.I):
        return f"<a href=\"{e(url)}\" target=\"_blank\" rel=\"noopener\">{e(url)}</a>"
    return e(url)  # jiná schémata (javascript:, data: ...) jen jako text


def _link_email(addr):
    addr = (addr or "").strip()
    if addr and _EMAIL_RE.match(addr):
        return f"<a href=\"mailto:{e(quote(addr, safe='@+'))}\">{e(addr)}</a>"
    return e(addr)


def _kraj_key(k):
    return unicodedata.normalize("NFKD", k).encode("ascii", "ignore").decode().lower()


def _kontakty(d):
    return [k for k in (d.get("kontakty") or []) if isinstance(k, dict)]


def _sec_prilezitosti(d):
    kont = _kontakty(d)
    if not kont:
        return _section("prilezitosti", "Nové příležitosti",
                        "<p class=\"muted\">Databáze kontaktů zatím není nahraná.</p>")
    s_emailem = sum(1 for k in kont if (k.get("email") or "").strip())
    v_kont = sum(1 for k in kont if k.get("v_kontaktu"))
    typy = Counter(_typ(k.get("typ")) for k in kont)
    typ_txt = ", ".join(f"{e(t)} {n}" for t, n in sorted(typy.items(), key=lambda x: (-x[1], x[0])))
    body = (f"<div class=\"prehled\"><p><strong>{len(kont)}</strong>celkem</p>"
            f"<p><strong>{s_emailem}</strong>s e-mailem</p><p><strong>{v_kont}</strong>v kontaktu</p></div>"
            f"<p>Celkem: <strong>{len(kont)}</strong> · s e-mailem: <strong>{s_emailem}</strong> · "
            f"v kontaktu: <strong>{v_kont}</strong></p><p>Podle typu: {typ_txt}</p>"
            "<p><a href=\"#seznam-prilezitosti\">Přejít na seznam příležitostí podle krajů ↓</a></p>")
    return _section("prilezitosti", "Nové příležitosti", body)


def _sec_seznam(d):
    kont = _kontakty(d)
    if not kont:
        return ""
    kraje = {}
    for k in kont:
        kraje.setdefault((k.get("kraj") or "").strip() or "Bez kraje", []).append(k)
    body = ""
    for kraj in sorted(kraje, key=_kraj_key):
        rows = []
        for k in sorted(kraje[kraj], key=lambda x: (_kraj_key(x.get("mesto") or ""), _kraj_key(x.get("nazev") or ""))):
            kontakt = [x for x in (_link_email(k.get("email")), e(k.get("telefon"))) if x]
            stav = ("<span class=\"st st-contact\">v kontaktu</span>" if k.get("v_kontaktu")
                    else "<span class=\"st st-new\">nový</span>")
            rows.append(f"<tr><th scope=\"row\">{e(k.get('nazev'))}</th><td>{e(_typ(k.get('typ')))}</td>"
                        f"<td>{e(k.get('mesto'))}</td><td>{'<br>'.join(kontakt)}</td>"
                        f"<td>{_link_web(k.get('web'))}</td><td>{stav}</td></tr>")
        body += (f"<details><summary>{e(kraj)} ({len(kraje[kraj])})</summary><div class=\"tw\"><table><thead><tr>"
                 "<th scope=\"col\">Název</th><th scope=\"col\">Typ</th><th scope=\"col\">Město</th>"
                 "<th scope=\"col\">Kontakt</th><th scope=\"col\">Web</th><th scope=\"col\">Stav</th>"
                 f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div></details>")
    return (f"<section class=\"siroka\" id=\"seznam-prilezitosti\" aria-labelledby=\"seznam\">"
            f"<h2 id=\"seznam\">Příležitosti podle krajů</h2>{body}</section>")


OBNOVIT_URL ="https://github.com/metropolitnidivadlo/email-asistent/actions/workflows/kokpit.yml"


def _kpi(d):
    f = d.get("folders", {})
    r = d.get("reply", {})
    avg = f"{e(r['avg_hours']).replace('.', ',')} h" if r.get("avg_hours") is not None else "–"
    dr = d.get("drafts", {"count": 0})
    cards = [
        (e(f.get("INBOX", {}).get("today", 0)), "Nové dnes"),
        (e(dr.get("count", 0)), "Koncepty čekají"),
        (e(len(d.get("important_today", []))), "Důležité dnes"),
        (e(f.get(NABIDKY, {}).get("week", 0)), "Nabídky a objednávky (týden)"),
        (avg, "Průměrná doba odpovědi"),
    ]
    return ("<ul class=\"kpi\" aria-label=\"Klíčová čísla\">"
            + "".join(f"<li><span class=\"kpi-v\">{v}</span><span class=\"kpi-l\">{l}</span></li>" for v, l in cards)
            + "</ul>")


def render(data):
    gen = data.get("generated") or config.now_prague().isoformat()
    note = " (náhled z dat zkoušky)" if data.get("source") == "zkouska" else ""
    left = _sec_koncepty(data) + _sec_ukoly(data) + _sec_dnes(data) + _sec_posta(data)
    right = _sec_predstaveni(data) + _sec_stat(data) + _sec_prilezitosti(data)
    return (
        "<!DOCTYPE html>\n<html lang=\"cs\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<meta name=\"color-scheme\" content=\"light dark\"><meta name=\"robots\" content=\"noindex\">"
        "<meta http-equiv=\"refresh\" content=\"300\">"
        "<title>Kokpit – Metropolitní divadlo</title>"
        "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">"
        "<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>"
        "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Karla:wght@400;500;600;700&display=swap\">"
        f"<style>{CSS}</style></head><body>"
        "<header class=\"bar\"><div class=\"bar-in\">"
        "<h1>METROPOLITNÍ DIVADLO PRAHA <span>· KOKPIT</span></h1>"
        "<div class=\"bar-r\">"
        f"<p class=\"gen\">Aktualizováno: <time>{e(_fmt_full(gen))}</time> ({e(config.TZ_NAME)}){e(note)}</p>"
        f"<a class=\"btn\" href=\"{e(OBNOVIT_URL)}\" target=\"_blank\" rel=\"noopener\">Aktualizovat teď</a>"
        "</div></div></header>"
        f"<main>{_kpi(data)}"
        f"<div class=\"grid\"><div class=\"col\">{left}</div><div class=\"col\">{right}</div></div>"
        f"{_sec_seznam(data)}"
        "<p class=\"muted\">Data se obnovují každých 15 min, stránka se sama načte každých 5 min. "
        "Na GitHubu u „Aktualizovat teď“ klikněte Run workflow, hotovo do ~1 min.</p></main></body></html>\n"
    )
