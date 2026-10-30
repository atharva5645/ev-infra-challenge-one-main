@echo off
echo Starting EV Infra Map Backend...
cd backend
call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause

