@echo off
call venv\Scripts\activate.bat
start "EquipmentDashboard" python run.py %*
