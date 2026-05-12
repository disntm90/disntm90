@echo off
REM ============================================================
REM 이 스크립트는 인터넷이 되는 PC에서 먼저 실행하세요
REM → wheels\ 폴더 생성됨 → 폴더째로 VM에 복사 → 아래 2단계 실행
REM ============================================================

REM [1단계] 인터넷 PC에서: 패키지 다운로드
REM   python -m pip download -r requirements.txt -d wheels\

REM [2단계] VM(내부망)에서: 오프라인 설치
if exist wheels\ (
    python -m venv venv
    call venv\Scripts\activate
    pip install --no-index --find-links=wheels -r requirements.txt
    echo.
    echo [완료] 오프라인 설치 성공. 이제 python run.py 로 실행하세요.
) else (
    echo [오류] wheels\ 폴더가 없습니다.
    echo 인터넷 PC에서 먼저 아래 명령을 실행하세요:
    echo   python -m pip download -r requirements.txt -d wheels\
    echo 그 후 wheels\ 폴더를 이 디렉토리에 복사하세요.
)
pause
