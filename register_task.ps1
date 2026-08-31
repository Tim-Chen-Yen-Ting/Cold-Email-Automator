$action = New-ScheduledTaskAction -Execute "D:\Cold Email\run_scheduler.bat" -WorkingDirectory "D:\Cold Email"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName "ColdEmailScheduler" -Action $action -Trigger $trigger -Settings $settings -User "$env:USERDOMAIN\$env:USERNAME" -RunLevel Limited -Force
Get-ScheduledTask -TaskName "ColdEmailScheduler" | Select-Object TaskName, State
