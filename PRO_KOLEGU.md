# E-mailový asistent Metropolitního divadla – přehled pro kolegu

Ahoj, tohle je e-mailový asistent pro šéfa Metropolitního divadla Praha. Prosím o kontrolu a návrhy vylepšení.
Na konci je **hotový prompt**: stačí si repozitář naklonovat a vložit prompt do Claude Code.

## Co to dělá
- **Pošta (IMAP, WEDOS `wes1-imap.wedos.net`):** nové e-maily z Doručené pošty třídí do složek *Představení a zájezdy, Doprava, Nabídky a objednávky, Faktury a finance, Ostatní, Newslettery*.
- **Koncepty odpovědí** píše ve stylu šéfa, který se naučil z odeslané pošty. Ukládá je do složky *Koncepty*, takže jsou vidět v Outlooku. Chybějící fakta (ceny, termíny) označí `[DOPLNIT: …]`.
- **Telegram:** po každém průchodu pošle souhrn. Ke každému konceptu přijde karta s tlačítky ✅ Odeslat / 🗑 Zahodit. Odeslání se ještě jednou potvrzuje, mail pak odejde přes SMTP WEDOS. Koncept s `[DOPLNIT]` se odeslat nedá.
- **Kokpit:** statická stránka na GitHub Pages, šifrovaná přes staticrypt heslem z GitHub Secrets. Obsahuje KPI, koncepty k odeslání, úkoly, poštu podle složek, statistiky a *Nové příležitosti* (databázi kulturních domů a divadel v ČR).
- **Souhrny a úkoly:** ukládají se soukromě do schránky (složky *Asistent - Souhrny / Úkoly / Kontakty*), protože repozitář je veřejný. Naplánovaná úloha v aplikaci Claude z nich ráno a večer udělá úkoly a připomínky.
- **AI:** Claude Code CLI (`claude -p`, model Haiku) běží na předplatném přes `CLAUDE_CODE_OAUTH_TOKEN`, ne přes placené API.

## Architektura
| Část | Soubor |
|---|---|
| CLI (zkouska, ostre, slozky, styl, kokpit, souhrny, ukoly, kontakty, telegram-akce) | `run.py`, `asistent/run.py` |
| IMAP, UTF-7 názvy složek | `asistent/imap_client.py`, `asistent/utf7.py` |
| Třídění (pravidla + AI) | `asistent/classify.py` |
| Styl a koncepty | `asistent/style.py`, `asistent/drafts.py`, `znalosti/divadlo.md` |
| Telegram, schvalování, SMTP | `asistent/telegram.py`, `asistent/telegram_akce.py`, `asistent/smtp_send.py` |
| Kokpit | `asistent/kokpit.py`, `asistent/kokpit_data.py`, `znalosti/branding.md` |
| Souhrny, úkoly, kontakty ve schránce | `asistent/souhrny.py`, `asistent/kontakty.py` |
| Moduly (hooky pro další sektory) | `asistent/modules/` |
| Běh v cloudu | `.github/workflows/asistent.yml`, `kokpit.yml`, `telegram.yml` |
| Spouštěč na PC (cron GitHubu se zpožďuje až o hodinu) | `spoustec/` |
| Testy | `tests/` (`python -m unittest discover -s tests`) |

**Bezpečnostní zásady:** hesla jsou jen v Klíčence Windows nebo v GitHub Secrets. V repozitáři nejsou žádná data z pošty (`data/` je v `.gitignore`). Asistent zpracovává jen zprávy s UID > `vars.ASISTENT_OD_UID`, aby nesáhl na staré maily. Bez potvrzení v Telegramu nic neodesílá.

## Známá slabá místa
- Bezplatný GitHub spouští cron zhruba jednou za hodinu, proto je na PC Plánovač úloh. Lepší by byl externí spouštěč (např. cron-job.org) nebo jiný hosting.
- Pokud se koncept upraví v Outlooku, hlavička `X-Asistent-Id` se může ztratit a tlačítko v Telegramu koncept nenajde.
- Profil stylu je v secretu `ASISTENT_STYL` a ručně se neobnovuje.
- Databáze kontaktů má 198 záznamů. Slabě pokryté jsou Praha, Karlovarský, Olomoucký, Liberecký a Plzeňský kraj. Chybí festivaly a sokolovny.
- Kokpit je statický, bez interakce (nemá JS ani backend).

---

## Prompt na vylepšení (vlož do Claude Code ve složce repozitáře)

```
Jsi senior Python vývojář a reviewer. V této složce je e-mailový asistent pro šéfa
zájezdového divadla (přečti PRO_KOLEGU.md a README.md). Komunikuj česky.

1. Projdi celý kód a testy (python -m unittest discover -s tests). Ke schránce se
   nepřipojuj a nic neodesílej – nemáš hesla a nemáš je ani zjišťovat.
2. Udělej review a seřaď nálezy podle závažnosti:
   a) bezpečnost (úniky dat do veřejného repa / logů, Telegram callbacky jen z povoleného
      chatu, SMTP odesílání jen po dvojím potvrzení, escapování v kokpitu, prompt injection
      z obsahu e-mailů do AI),
   b) spolehlivost (IMAP chyby, duplicitní zpracování, souběh workflow, idempotence
      odesílání, chování při výpadku Claude CLI),
   c) kvalita koncepty odpovědí a třídění (prompty v classify.py / drafts.py),
   d) UX kokpitu (asistent/kokpit.py) – přehlednost, mobil, WCAG 2.1 AA,
   e) architektura a modularita (asistent/modules) pro další sektory: CRM kontaktů,
      hledání nových klientů (kulturní domy), generování promptů pro grafiku, finance.
3. Navrhni konkrétní vylepšení s odhadem přínosu a náročnosti. Nejpřínosnější malé opravy
   rovnou implementuj s testy, větší věci popiš jako plán.
4. Výsledek shrň do souboru REVIEW.md a změny dej do samostatné větve / pull requestu.
```
