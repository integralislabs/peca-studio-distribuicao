@echo off
cd /d "%~dp0"
if not exist ".runtime\Scripts\python.exe" python -m venv .runtime
if errorlevel 1 exit /b 1
".runtime\Scripts\python.exe" -m pip install -r requirements-local.txt
if errorlevel 1 exit /b 1
echo Recursos locais preparados. OCR usa Tesseract instalado no computador.
pause
