@echo off
cd /d %~dp0
python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python tools\generate_demo_evidence.py
pause
