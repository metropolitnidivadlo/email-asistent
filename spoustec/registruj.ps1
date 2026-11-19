# Založí v Plánovači úloh Windows úlohu "Email asistent - spoustec" (jen pro vašeho uživatele, bez správce).
# Každých 5 minut spustí skrytě spoustec.vbs -> spoustec.ps1 (spouští workflow na GitHubu, nic neodesílá).
# Odebrání: Unregister-ScheduledTask -TaskName "Email asistent - spoustec" -Confirm:$false
$vbs = Join-Path $PSScriptRoot "spoustec.vbs"
$a = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbs`""
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(7) -RepetitionInterval (New-TimeSpan -Minutes 5)
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
     -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
Register-ScheduledTask -TaskName "Email asistent - spoustec" -Action $a -Trigger $t -Settings $s `
  -Description "Každých 5 min spouští workflow e-mailového asistenta na GitHubu (Telegram 5 min, pošta a kokpit 15 min, 7-22 h)." -Force | Out-Null
Start-ScheduledTask -TaskName "Email asistent - spoustec"
Start-Sleep 12
Write-Host "Úloha založena. Poslední záznamy:"
Get-Content (Join-Path $PSScriptRoot "spoustec.log") -Tail 5
