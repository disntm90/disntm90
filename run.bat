@echo off
REM Windows Server에서 실행하는 배치 파일
REM 가상환경 활성화 후 실행
call venv\Scripts\activate.bat
python run.py %*
pause
