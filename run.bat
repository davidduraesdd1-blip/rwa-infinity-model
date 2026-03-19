@echo off
title RWA Infinity Model v1.0
color 0B

echo.
echo  ♾  RWA INFINITY MODEL v1.0
echo  Real World Asset Intelligence Platform
echo  ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

:: Set API key from .env if present
if exist .env (
    echo  Loading environment from .env...
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        set "%%a=%%b"
    )
)

:: Install/upgrade dependencies
echo  Checking dependencies...
pip install -r requirements.txt -q --upgrade

echo.
echo  Starting RWA Infinity Model...
echo  Open browser at: http://localhost:8501
echo.

streamlit run app.py --server.port 8501 --server.headless false

pause
