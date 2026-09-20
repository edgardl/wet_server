@echo off
setlocal
cd /d "%~dp0desktop-pet"
python -m pip install --target vendor -r requirements.txt
if errorlevel 1 pause & exit /b 1
start "Desktop Lonk Birds" pythonw desktop_pet.py
endlocal