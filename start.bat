@echo off
cd /d "%~dp0"
py -3.13 main.py
if errorlevel 1 (
  echo.
  echo Не удалось запустить. Нужен Python 3.13 и пакеты из requirements.txt
  echo Команда: py -3.13 -m pip install -r requirements.txt
  pause
)
