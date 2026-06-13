@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  Cycle Checklist - Monthly data update
echo  (FRED + yfinance fetch, rebuild HTML)
echo ============================================
python run_monthly.py
echo.
pause
