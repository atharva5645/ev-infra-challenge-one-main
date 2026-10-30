@echo off
echo Starting EV Infra Map India (Backend + Frontend)...
start "EV Infra Backend" cmd /k "%~dp0run-backend.bat"
start "EV Infra Frontend" cmd /k "%~dp0run-frontend.bat"

