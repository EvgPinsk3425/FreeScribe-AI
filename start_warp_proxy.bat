@echo off
cd /d "%~dp0warp-socks"
if not exist wireproxy.exe (
  echo wireproxy.exe not found in warp-socks
  pause
  exit /b 1
)
if not exist wireproxy.conf (
  echo wireproxy.conf not found
  pause
  exit /b 1
)
echo Starting local SOCKS5 on 127.0.0.1:40000
echo This does not change server routes and does not need Administrator.
start "" /MIN wireproxy.exe -c "%cd%\wireproxy.conf"
timeout /t 2 /nobreak >nul
echo Done. In FreeScribe-AI settings use:
echo socks5://127.0.0.1:40000
pause
