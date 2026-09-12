#!/bin/bash
cd "$(dirname "$0")"
echo "F1 Whisper Typing — macOS"
python3 -m pip install -r requirements.txt
exec python3 main.py
