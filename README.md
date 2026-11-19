# E-mailový asistent Metropolitního divadla

Třídí poštu ze schránky info@metropolitnidivadlo.cz (WEDOS), ukládá koncepty odpovědí do složky
"Koncepty" a posílá souhrn do Telegramu. **E-mailem odešle výhradně koncept, který uživatel v Telegramu dvakrát potvrdil (viz „Schvalování v Telegramu“); nic jiného se neodesílá.**

## Lokální spuštění (Windows)

```powershell
$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
& $py -m pip install --user -r requirements.txt
& $py imap_core.py setup                 # jednou: uloží IMAP údaje do Klíčenky
```

AI běží přes Claude Code CLI (`claude`, předplatné, bez API klíče). Pokud `claude` není na PATH,
asistent třídí jen podle pravidel/klíčových slov a nevytváří koncepty.

Příkazy:

- `python run.py zkouska --pocet 10` - nanečisto, nic se ve schránce nemění; výstup `data/zkouska.md` a `data/zkouska.json`
- `python run.py slozky [--vytvor]` - stav složek, s `--vytvor` vytvoří chybějící
- `python run.py vzorky-stylu --pocet 30` - uloží texty odeslané pošty do `data/styl_vzorky.json` (bez AI); `zkouska` navíc ukládá `data/zkouska_vstup.json`
- `python run.py styl` - přegeneruje profil stylu do `data/styl.md`
- `$env:ASISTENT_OSTRE="1"; python run.py ostre [--ignoruj-cas]` - ostrý běh (třídí, ukládá koncepty)

Model lze změnit proměnnou `ASISTENT_MODEL` (výchozí `claude-haiku-5-5`).

## GitHub Actions

Repozitář > Settings > Secrets and variables > Actions > New repository secret:
`IMAP_USER`, `IMAP_PASSWORD`, `CLAUDE_CODE_OAUTH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
`CLAUDE_CODE_OAUTH_TOKEN` získáte lokálně příkazem `claude setup-token` (předplatné Pro/Max).
Workflow si nainstaluje Node 20 a `@anthropic-ai/claude-code`.
Workflow `.github/workflows/asistent.yml` běží každých 30 minut (cron v UTC), kód sám skončí mimo 7-22 h
Europe/Prague. Ruční spuštění: záložka Actions > Run workflow (mimo okno použijte lokálně `--ignoruj-cas`).
Pozor: `data/` se v Actions neukládá, profil stylu se proto tam generuje při každém běhu, kde je potřeba koncept.

## Kokpit

Statická stránka (Dnes, Pošta, Představení a doprava, Statistiky a finance) na GitHub Pages, zašifrovaná
heslem (staticrypt). Schránku jen čte (readonly, bez těl zpráv), nic neodesílá ani nemění.

- Lokální náhled bez připojení: `python run.py kokpit --z-zkousky --vystup data/kokpit_nahled.html`
- Ze schránky: `python run.py kokpit [--vystup site/index.html]`
- Workflow `.github/workflows/kokpit.yml` běží každých 30 minut (UTC 4-21) a ručně (Actions > Run workflow).
- Nastavení: přidejte secret `KOKPIT_HESLO` (vedle `IMAP_USER`, `IMAP_PASSWORD`); bez něj workflow selže
  a nic se nepublikuje. Zapněte Pages: Settings > Pages > Source: **GitHub Actions**.
- Repozitář musí být veřejný, aby Pages fungovaly zdarma. V repu nejsou žádná data ani hesla:
  `data/`, `site/` a `.env` jsou v `.gitignore`; nešifrovaná verze (`site/index.html`) se nikdy necommituje
  a do artifactu se nahrává jen `site/out` (zašifrováno).
- Pozor: kokpit v Actions nemá trvalé úložiště, "Dnes důležité" proto vychází z příznaku Flagged ve schránce
  (a z `data/log.jsonl`, pokud existuje, tj. jen lokálně).

## Telegram

1. V Telegramu napište `@BotFather`, příkaz `/newbot`, zvolte jméno; dostanete token (`TELEGRAM_BOT_TOKEN`).
2. Svému botovi napište libovolnou zprávu (např. `/start`).
3. Otevřete v prohlížeči `https://api.telegram.org/bot<TOKEN>/getUpdates` a najděte `"chat":{"id":...}` - to je `TELEGRAM_CHAT_ID`.
4. Obě hodnoty uložte jako GitHub Secrets (nebo do Klíčenky pod názvy `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).

## Schvalování v Telegramu

Každý nový koncept dostane id v hlavičce `X-Asistent-Id` a do Telegramu přijde karta (od koho, předmět, shrnutí,
text konceptu do 3500 znaků) s tlačítky [✅ Odeslat] a [🗑 Zahodit].

- Odeslat > „Opravdu odeslat na …?“ > [Ano, odeslat] / [Zpět]. Teprve „Ano“ odešle koncept přes SMTP
  (`wes1-smtp.wedos.net:465`, jiný host přes `SMTP_HOST`; stejné přihlášení jako IMAP). Koncept se smaže z Koncepty,
  kopie jde do Odeslaných (`\Seen`), původní mail dostane `\Answered`.
- Koncept, který už ve složce není (smazán/odeslán v Outlooku), se neodešle. Koncept s `[DOPLNIT]` se neodešle
  (doplňte ho v Outlooku). Selže-li SMTP, koncept zůstává a přijde „❌ Odeslání selhalo“.
- Když koncept v Outlooku upravíte a hlavička `X-Asistent-Id` se ztratí, tlačítko ho nenajde; odešlete ho v Outlooku.
- `python run.py telegram-akce` zpracuje čekající kliknutí (přijímá jen `TELEGRAM_CHAT_ID`, updates potvrdí hned po
  načtení, takže se akce neopakuje). `--nanecisto` jen vypíše, nic nepotvrdí ani neodešle (lokálně používejte jen to).
- Workflow `telegram.yml` běží každých 5 min (UTC 4-21), navíc krok před „Ostrým během“ v `asistent.yml`.

## Souhrny a úkoly

Repo je veřejné, proto se souhrny a úkoly ukládají soukromě do schránky (plochých složek, vytváří je
`slozky --vytvor` a `ostre`): `Asistent - Souhrny` a `Asistent - Úkoly`. Každá zpráva obsahuje čitelný text
a na konci JSON mezi řádky `---JSON---` a `---/JSON---`. Nic se neodesílá, jen se ukládá (APPEND, `\Seen`).

- `ostre` po zpracování ≥ 1 zprávy uloží souhrn (selhání uložení běh neshodí).
- `python run.py souhrny --dni 1 [--vystup data/souhrny.json]` - readonly přečte souhrny za N dní.
- `python run.py ukoly-ulozit soubor.json [--telegram]` - zvaliduje (max 30 úkolů, text max 300 znaků,
  priorita vysoká/střední/nízká, termín `YYYY-MM-DD` nebo null), uloží a volitelně pošle do Telegramu.
  Formát: `{"vytvoreno": "...", "ukoly": [{"text", "termin", "priorita", "zdroj"}], "poznamka": "..."}`.
- `python run.py ukoly` - readonly vypíše poslední uložené úkoly.
- Kokpit v sekci „Dnes“ zobrazuje poslední úkoly (vysoká priorita zvýrazněna, prošlé termíny „po termínu“).

## Rozšíření

Nové sektory (finance, vstupenky) přidejte jako modul v `asistent/modules/` s funkcemi
`on_email(email, result)` a `on_run_end(results)` a zaregistrujte v `modules.load_default()`.
