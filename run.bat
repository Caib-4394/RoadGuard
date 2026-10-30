@echo off
echo ==========================================
echo   RoadGuard - Road Damage Detection System
echo ==========================================
echo.
cd /d "%~dp0"
streamlit run app\main.py --server.maxUploadSize 200 --server.address 127.0.0.1 --server.port 8502
pause
