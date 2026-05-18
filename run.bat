@echo off
REM Windows Server에서 실행하는 배치 파일
REM 가상환경 활성화 후 실행

call venv\Scripts\activate.bat

REM pythonw.exe: 콘솔 창 없이 실행 → stdin이 NUL로 고정되어
REM SSH/터미널 세션 종료 시 [WinError 233] 파이프 에러를 방지한다.
REM 로그는 logs\ 폴더에 기록되므로 콘솔 출력이 없어도 문제없다.
start "" pythonw run.py %*
