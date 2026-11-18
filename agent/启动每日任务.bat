@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\JF\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe
if not exist "%PY%" set PY=python

echo ============================================
echo  不止攀岩 - 新媒体每日数据（抖音 + 小红书）
echo ============================================
echo.
echo [1/2] 检查 data\inbox 里的导出文件...
dir /b data\inbox\*.csv 2>nul
if errorlevel 1 echo   （没有 CSV，今天的素材会记 0 条）
echo.
echo [2/2] 开始写入飞书...
"%PY%" daily_job.py %*
echo.
echo 日志： data\logs\
echo ============================================
pause
