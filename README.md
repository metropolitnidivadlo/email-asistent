# E-mailový asistent Metropolitního divadla

Třídí poštu ze schránky info@metropolitnidivadlo.cz (WEDOS), ukládá koncepty odpovědí do složky
"Koncepty" a posílá souhrn do Telegramu. **Nikdy nic neodesílá e-mailem.**

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

## Rozšíření

Nové sektory (finance, vstupenky) přidejte jako modul v `asistent/modules/` s funkcemi
`on_email(email, result)` a `on_run_end(results)` a zaregistrujte v `modules.load_default()`.
