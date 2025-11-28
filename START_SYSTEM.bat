@echo off
echo ========================================
echo   Traffic Vision System - Startup
echo ========================================
echo.

echo [1/3] Starting Backend Server...
start cmd /k "cd backend && python server.py"
timeout /t 3 /nobreak >nul

echo [2/3] Starting Frontend Dashboard...
start cmd /k "cd frontend && npm start"
timeout /t 2 /nobreak >nul

echo [3/3] System Starting...
echo.
echo ========================================
echo   System URLs:
echo   Backend:  http://localhost:5000
echo   Frontend: http://localhost:3000
echo ========================================
echo.
echo Press any key to exit this window...
pause >nul
