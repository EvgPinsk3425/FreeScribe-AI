@echo off
cd /d "%~dp0"
py -3.13 -m pip install -r requirements.txt
if errorlevel 1 python -m pip install -r requirements.txt
py -3.13 -m PyInstaller --noconfirm WhisperTyping.spec
if errorlevel 1 python -m PyInstaller --noconfirm WhisperTyping.spec
pause
