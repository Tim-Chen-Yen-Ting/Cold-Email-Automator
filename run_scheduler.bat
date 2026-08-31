@echo off
cd /d "D:\Cold Email"
echo. >> logs\scheduler.log
echo ==== started %date% %time% ==== >> logs\scheduler.log
".venv\Scripts\python.exe" -u scheduler.py >> logs\scheduler.log 2>&1
