# Spouštěč běhů na GitHubu (GitHub na bezplatném účtu plánované běhy zpožďuje až o hodinu).
# Plánovač úloh Windows ho volá každých 5 minut. Nic neodesílá, jen spouští workflow.
$ErrorActionPreference = "SilentlyContinue"
$gh   = "C:\Program Files\GitHub CLI\gh.exe"
$repo = "metropolitnidivadlo/email-asistent"
$log  = Join-Path $PSScriptRoot "spoustec.log"
$now  = Get-Date
if ($now.Hour -lt 7 -or $now.Hour -ge 22) { exit 0 }

function Spust($wf) {
    & $gh workflow run $wf --repo $repo 2>&1 | Out-Null
    Add-Content $log ("{0:yyyy-MM-dd HH:mm}  {1}  exit={2}" -f (Get-Date), $wf, $LASTEXITCODE) -Encoding utf8
}

Spust "telegram.yml"                     # schválení z Telegramu: každých 5 min
if ($now.Minute % 15 -lt 5) {            # pošta a kokpit: každých 15 min
    Spust "asistent.yml"
    Spust "kokpit.yml"
}
# log držet krátký
if ((Get-Item $log).Length -gt 200KB) { Get-Content $log -Tail 500 | Set-Content $log -Encoding utf8 }
