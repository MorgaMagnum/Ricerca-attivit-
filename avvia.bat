@echo off
cd /d "%~dp0"
echo Avvio Local Business Finder...
echo Apri il browser su: http://localhost:5000
echo Premi CTRL+C per fermare.
echo.
python app.py
pause
