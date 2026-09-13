#!/bin/bash
cd "$(dirname "$0")"
echo "FreeScribe-AI — macOS"
python3 -m pip install -r requirements.txt
exec python3 main.py
