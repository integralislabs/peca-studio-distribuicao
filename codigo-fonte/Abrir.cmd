@echo off
cd /d "%~dp0"
if exist ".runtime\Scripts\python.exe" (start "Peca Studio" /min ".runtime\Scripts\python.exe" server.py) else (start "Peca Studio" /min python server.py)
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:17865"
