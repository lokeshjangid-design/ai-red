@echo off
echo ========================================
echo   Traffic Vision System - Setup
echo ========================================
echo.

echo [1/2] Installing Backend Dependencies...
cd backend
pip install -r requirements.txt
cd ..
echo Backend setup complete!
echo.

echo [2/2] Installing Frontend Dependencies...
cd frontend
call npm install
cd ..
echo Frontend setup complete!
echo.

echo ========================================
echo   Setup Complete!
echo   Run START_SYSTEM.bat to launch
echo ========================================
pause
