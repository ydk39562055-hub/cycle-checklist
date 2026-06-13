@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Cycle Checklist
python start.py
pause
