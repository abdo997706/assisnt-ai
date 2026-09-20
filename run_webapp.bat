@echo off
cd /d "%~dp0"
echo ============================================
echo   Installing required packages (first time only)...
echo ============================================
python -m pip install -r requirements.txt
echo.
echo Starting web server...
start "" cmd /c "timeout /t 2 >nul && start http://localhost:8000"
python -m uvicorn server:app --reload --port 8000
pause
