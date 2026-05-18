@echo off
git pull origin main
call venv\Scripts\activate.bat
start "EquipmentDashboard" python run.py %*
