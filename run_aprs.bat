@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
title APRS - Autonomous Product Research System

echo ===================================================
echo   APRS - E-Commerce Intelligence Dashboard
echo ===================================================
echo [1] Checking Virtual Environment...
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.\.venv\Scripts\python.exe"
    set "ST_EXE=.\.venv\Scripts\streamlit.exe"
) else (
    set "PY_EXE=python"
    set "ST_EXE=streamlit"
)

echo [2] Initializing Database Schema (Safe Check)...
%PY_EXE% -c "from core.database import init_db; init_db(); print('Database ready.')"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Database initialization failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ===================================================
echo [3] Launching APRS Streamlit Dashboard...
echo URL: http://localhost:8501
echo ===================================================
echo Press Ctrl+C in this terminal to stop the server.
echo.

%ST_EXE% run web\app.py --server.port 8501

pause
