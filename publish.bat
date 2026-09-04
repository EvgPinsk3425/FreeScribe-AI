@echo off
cd /d "%~dp0"
echo === Публикация F1 Whisper Typing на GitHub ===
echo.

where gh >nul 2>&1
if errorlevel 1 (
  echo gh CLI не найден. Установите: https://cli.github.com/
  echo Или: pip install gh  — нет, нужен официальный gh
  pause
  exit /b 1
)

gh auth status >nul 2>&1
if errorlevel 1 (
  echo Сначала войдите в GitHub:
  gh auth login
  echo.
)

gh repo create F1WhisperTyping --public --source=. --remote=origin --push --description "Offline voice typing for Windows (faster-whisper)"
if errorlevel 1 (
  echo.
  echo Если репозиторий уже есть, выполните:
  echo   git remote add origin https://github.com/ВАШ_ЛОГИН/F1WhisperTyping.git
  echo   git push -u origin master
)
pause
