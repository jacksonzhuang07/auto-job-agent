$Action = New-ScheduledTaskAction -Execute "python.exe" -Argument "main.py" -WorkingDirectory "C:\Users\anbil\.gemini\antigravity\scratch\auto-job-agent"
$Trigger = New-ScheduledTaskTrigger -Daily -At 8:00AM
Register-ScheduledTask -TaskName "DailyJobApplierAgent" -Action $Action -Trigger $Trigger -Description "Autonomous Job Applier Agent for LinkedIn and Indeed" -Force
Write-Host "[OK] DailyJobApplierAgent successfully registered with Windows Task Scheduler!"
