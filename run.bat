@echo off
call venv\Scripts\activate.bat
start "EquipmentDashboard" pythonw run.py %*
