"""Vykreslení kokpitu do jednoho samostatného HTML (inline CSS, bez externích zdrojů a bez JS)."""
from datetime import datetime
from html import escape as _esc

from . import config

# Barvy; test v tests/test_kokpit.py z nich počítá kontrast podle WCAG 2.1.
PALETTES = {
    "light": {"bg": "#ffffff", "fg": "#1b1b1b", "muted": "#4d4d4d", "box": "#f5f5f5", "border": "#4d4d4d",
              "rule": "#767676", "head": "#0a3069", "th": "#e2e2e2", "badge_bg": "#8a1c1c",
              "badge_fg": "#ffffff"},
    "dark": {"bg": "#121212", "fg": "#f0f0f0", "muted": "#bdbdbd", "box": "#1e1e1e", "border": "#a0a0a0",
             "rule": "#8a8a8a", "head": "#9ec1ff", "th": "#2e2e2e", "badge_bg": "#ffb3ad",
             "badge_fg": "#3a0905"},
}
# (popředí, pozadí, minimální poměr): text >= 4.5, okraje a ikonky >= 3
PAIRS = [
    ("fg", "bg", 4.5), ("fg", "box", 4.5), ("muted", "bg", 4.5), ("muted", "box", 4.5),
    ("head", "box", 4.5), ("head", "bg", 4.5), ("fg", "th", 4.5), ("muted", "th", 4.5),
    ("badge_fg", "badge_bg", 4.5), ("border", "bg", 3), ("border", "box", 3), ("rule", "box", 3),
    ("badge_bg", "box", 3),
]


def _vars(p):
    return "".join(f"--{k}:{v};" for k, v in p.items())


CSS = (
    ":root{" + _vars(PALETTES["light"]) + "color-scheme:light dark}"
    "@media (prefers-color-scheme:dark){:root{" + _vars(PALETTES["dark"]) + "}}"
    "*{box-sizing:border-box}"
    "body{margin:0;padding:1rem;background:var(--bg);color:var(--fg);"
    "font:1rem/1.5 system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;overflow-wrap:anywhere}"
    "main,header{max-width:60rem;margin:0 auto}"
    "h1{font-size:1.6rem;margin:0 0 .25rem}"
    ".gen{color:var(--muted);margin:0 0 1.5rem}"
    "section{border:2px solid var(--border);border-radius:8px;background:var(--box);"
    "padding:1rem;margin:0 0 2rem}"
    "section>h2{font-size:1.35rem;margin:0 0 1rem;padding-bottom:.5rem;color:var(--head);"
    "border-bottom:2px solid var(--border)}"
    "h3{font-size:1.1rem;margin:1.25rem 0 .5rem;color:var(--head)}"
    "table{border-collapse:collapse;width:100%;margin:0 0 1rem;font-size:.9rem}"
    "caption{text-align:left;font-weight:600;padding:.25rem 0}"
    "th,td{border:1px solid var(--rule);padding:.35rem .5rem;text-align:left;vertical-align:top}"
    "thead th{background:var(--th);color:var(--fg)}"
    "tbody th{font-weight:600;background:var(--th)}"
    "td.n,th.n{text-align:right}"
    ".nowrap{white-space:nowrap}"
    ".badge{display:inline-block;background:var(--badge_bg);color:var(--badge_fg);"
    "border-radius:4px;padding:0 .4rem;font-size:.8rem;font-weight:700;margin-right:.35rem}"
    ".muted{color:var(--muted)}"
    "p{margin:.25rem 0 .75rem}"
    "@media (max-width:480px){body{padding:.5rem}section{padding:.6rem}"
    "table{font-size:.8rem}th,td{padding:.25rem .3rem}}"
)

POSTA_ZBYTEK = ("INBOX", "Ostatní", "Newslettery")
DOPRAVA = ("Představení a zájezdy", "Doprava", "Nabídky a objednávky")
FINANCE = "Faktury a finance"


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
    return (f"<table><caption>{e(caption)}</caption><thead><tr>{head}</tr></thead>"
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
    return (f"<table><caption>{e(caption)}</caption><thead><tr><th scope=\"col\">Složka</th>"
            "<th scope=\"col\" class=\"n\">Dnes</th><th scope=\"col\" class=\"n\">7 dní</th>"
            f"<th scope=\"col\" class=\"n\">30 dní</th></tr></thead><tbody>{''.join(rows)}</tbody></table>")


def _section(sid, title, body):
    return (f"<section aria-labelledby=\"{sid}\"><h2 id=\"{sid}\">{e(title)}</h2>{body}</section>")


def _sec_dnes(d):
    imp = d.get("important_today", [])
    if imp:
        rows = "".join(
            f"<tr><th scope=\"row\" class=\"nowrap\">{e(_fmt(i['date']))}</th><td>{e(i['from'])}</td>"
            f"<td><span class=\"badge\">Důležité</span>{e(i['subject'])}"
            + (f"<br><span class=\"muted\">{e(i['summary'])}</span>" if i.get("summary") else "")
            + f"</td><td>{e(i.get('folder', ''))}</td></tr>" for i in imp)
        imp_html = ("<table><caption>Důležité dnes</caption><thead><tr><th scope=\"col\">Čas</th>"
                    "<th scope=\"col\">Od</th><th scope=\"col\">Předmět</th><th scope=\"col\">Složka</th>"
                    f"</tr></thead><tbody>{rows}</tbody></table>")
    else:
        imp_html = "<h3>Důležité dnes</h3><p class=\"muted\">Dnes nic důležitého.</p>"
    dr = d.get("drafts", {"count": 0, "items": []})
    if dr["items"]:
        rows = "".join(
            f"<tr><th scope=\"row\" class=\"nowrap\">{e(_fmt(i['date']))}</th><td>{e(i['to'])}</td>"
            f"<td>{e(i['subject'])}</td></tr>" for i in dr["items"])
        dr_html = (f"<table><caption>Čekající koncepty ({e(dr['count'])})</caption><thead><tr>"
                   "<th scope=\"col\">Datum</th><th scope=\"col\">Komu</th><th scope=\"col\">Předmět</th>"
                   f"</tr></thead><tbody>{rows}</tbody></table>")
    else:
        dr_html = "<h3>Čekající koncepty</h3><p class=\"muted\">Žádné koncepty nečekají.</p>"
    return _section("dnes", "Dnes", _ukoly_html(d) + imp_html + dr_html)


def _today(d):
    try:
        return datetime.fromisoformat(d.get("generated")).date()
    except Exception:
        return config.now_prague().date()


def _ukoly_html(d):
    """Podsekce 'Úkoly a připomínky'; vysoká priorita zvýrazněná textem i barvou, prošlé termíny 'po termínu'."""
    uk = d.get("ukoly") or {}
    items = uk.get("ukoly") or []
    if not items:
        return "<h3>Úkoly a připomínky</h3><p class=\"muted\">Zatím žádné úkoly.</p>"
    today = _today(d).isoformat()
    order = {"vysoká": 0, "střední": 1, "nízká": 2}
    items = sorted(items, key=lambda u: (order.get(u.get("priorita"), 9), u.get("termin") or "9999-99-99"))
    lis = []
    for u in items:
        prio = u.get("priorita")
        badge = "<span class=\"badge\">Vysoká priorita</span>" if prio == "vysoká" else (
            f"<span class=\"muted\">({e(prio)})</span> " if prio else "")
        txt = f"<strong>{e(u.get('text'))}</strong>" if prio == "vysoká" else e(u.get("text"))
        extra = ""
        t = u.get("termin")
        if t:
            if str(t) < today:
                extra += f" <span class=\"badge\">po termínu</span> termín {e(t)}"
            else:
                extra += f" <span class=\"muted\">termín {e(t)}</span>"
        if u.get("zdroj"):
            extra += f" <span class=\"muted\">[{e(u['zdroj'])}]</span>"
        lis.append(f"<li>{badge}{txt}{extra}</li>")
    note = f"<p class=\"muted\">{e(uk['poznamka'])}</p>" if uk.get("poznamka") else ""
    created = (f"<p class=\"muted\">Vytvořeno: {e(_fmt_full(uk['vytvoreno']))}</p>"
               if uk.get("vytvoreno") else "")
    return f"<h3>Úkoly a připomínky</h3><ul>{''.join(lis)}</ul>{note}{created}"


def _sec_posta(d):
    f = d.get("folders", {})
    body = _counts_table(f, ["INBOX"] + [n for n in config.FOLDERS])
    for n in POSTA_ZBYTEK:
        if n in f:
            body += _msg_table(f[n]["latest"], f"{_name(n)} - posledních {len(f[n]['latest'])} zpráv")
    return _section("posta", "Pošta", body)


def _sec_predstaveni(d):
    f = d.get("folders", {})
    body = _counts_table(f, DOPRAVA)
    for n in DOPRAVA:
        if n in f:
            body += _msg_table(f[n]["latest"], f"{n} - posledních {len(f[n]['latest'])} zpráv")
    return _section("predstaveni", "Představení a doprava", body)


def _senders(items, caption):
    if not items:
        return f"<p class=\"muted\">{e(caption)}: žádná data.</p>"
    rows = "".join(
        f"<tr><th scope=\"row\">{e(i['name'] or i['addr'])}"
        + (f"<br><span class=\"muted\">{e(i['addr'])}</span>" if i["name"] else "")
        + f"</th><td class=\"n\">{e(i['count'])}</td></tr>" for i in items)
    return (f"<table><caption>{e(caption)}</caption><thead><tr><th scope=\"col\">Odesílatel</th>"
            f"<th scope=\"col\" class=\"n\">Zpráv</th></tr></thead><tbody>{rows}</tbody></table>")


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
    ts = d.get("top_senders", {})
    body += _senders(ts.get("week", []), "Nejčastější odesílatelé - týden (top 5)")
    body += _senders(ts.get("month", []), "Nejčastější odesílatelé - měsíc (top 5)")
    if FINANCE in f:
        body += _counts_table(f, [FINANCE], "Faktury a finance - počty")
        body += _msg_table(f[FINANCE]["latest"], f"{FINANCE} - posledních {len(f[FINANCE]['latest'])} zpráv")
    return _section("statistiky", "Statistiky a finance", body)


def render(data):
    gen = data.get("generated") or config.now_prague().isoformat()
    note = " (náhled z dat zkoušky)" if data.get("source") == "zkouska" else ""
    sections = _sec_dnes(data) + _sec_posta(data) + _sec_predstaveni(data) + _sec_stat(data)
    return (
        "<!DOCTYPE html>\n<html lang=\"cs\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<meta name=\"color-scheme\" content=\"light dark\"><meta name=\"robots\" content=\"noindex\">"
        "<title>Kokpit – Metropolitní divadlo</title>"
        f"<style>{CSS}</style></head><body>"
        "<header><h1>Kokpit – Metropolitní divadlo</h1>"
        f"<p class=\"gen\">Vygenerováno: {e(_fmt_full(gen))} ({e(config.TZ_NAME)}){e(note)}</p></header>"
        f"<main>{sections}</main></body></html>\n"
    )
