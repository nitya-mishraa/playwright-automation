@echo off
echo.
echo  GeM Tender Intelligence Dashboard
echo  ===================================
echo.
cd /d "%~dp0"
python -m pip install flask --quiet
echo  Starting server at http://localhost:5000
echo  Press Ctrl+C to stop.
echo.
python app.py
pause
