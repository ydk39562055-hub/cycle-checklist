@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Opening checklist at http://localhost:8765  (close: Ctrl+C)
python serve.py
pause
