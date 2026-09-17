# Register AutoTrade AI - Start on Login Scheduled Task
$TaskName = "AutoTrade AI - Start on Login"
$ScriptPath = "D:\Trading LLM\MobiTradeAI\scripts\windows_start_autotrade.ps1"
$WorkDir = "D:\Trading LLM\MobiTradeAI"

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`"" -WorkingDirectory "$WorkDir"
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 4)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force
Write-Host "Task '$TaskName' registered successfully."
