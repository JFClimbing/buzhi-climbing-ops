# 一键创建 Windows 计划任务：每天 08:30 跑新媒体日报
# 用法（管理员 PowerShell）：powershell -ExecutionPolicy Bypass -File .\register_task.ps1
$ErrorActionPreference = "Stop"

$TaskName = "不止攀岩-新媒体日报"
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py  = "C:\Users\JF\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path $Py)) {
    Write-Host "找不到 Python：$Py" -ForegroundColor Red
    Write-Host "请把脚本里的 `$Py 改成你的 python.exe 绝对路径后再跑。" -ForegroundColor Yellow
    exit 1
}

$action = New-ScheduledTaskAction -Execute $Py -Argument "daily_job.py" -WorkingDirectory $Dir
$trigger = New-ScheduledTaskTrigger -Daily -At 08:30
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "每天抓抖音/小红书数据写入飞书多维表格（不止攀岩）" | Out-Null

Write-Host "已创建计划任务：$TaskName" -ForegroundColor Green
Write-Host "  时间：每天 08:30"
Write-Host "  程序：$Py"
Write-Host "  参数：daily_job.py（工作目录 $Dir）"
Write-Host ""
Write-Host "查看：schtasks /Query /TN `"$TaskName`""
Write-Host "立即测试：schtasks /Run /TN `"$TaskName`""
Write-Host "删除：schtasks /Delete /TN `"$TaskName`" /F"
Write-Host ""
Write-Host "注意：如果首次运行被杀毒/权限拦截，用「任务计划程序」界面手动确认一次即可。" -ForegroundColor Yellow
