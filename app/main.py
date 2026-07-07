"""
main.py — FastAPI 앱 생성 및 시작/종료 처리

앱 실행 흐름:
  1. 로그 설정
  2. lifespan 시작: bigdataquery 로그인 → DB 초기화 → 스케줄러 시작
  3. 라우터 등록 (URL 경로와 핸들러 연결)
  4. (앱 종료 시) 스케줄러 정지
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_db
from app.routers import equipment, deploy, logs, files, bdq, priority
from app.services.scheduler import start_scheduler, stop_scheduler, get_scheduler_status

# ── 로그 파일 디렉토리 사전 생성 ────────────────────────────────
# FileHandler 설정 전에 폴더가 없으면 FileNotFoundError가 발생하므로 미리 만든다.
os.makedirs("logs", exist_ok=True)

# ── 로깅 설정 ────────────────────────────────────────────────────
# 콘솔과 파일 양쪽에 동일한 포맷으로 출력한다.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),                               # 터미널 출력
        logging.FileHandler("logs/app.log", encoding="utf-8"), # 파일 출력
    ],
)


# ── 앱 생명주기 관리 ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan 컨텍스트 매니저.

    yield 이전 = 앱 시작 시 실행
    yield 이후 = 앱 종료 시 실행

    순서가 중요하다:
      1) bigdataquery 로그인 — DB 조회가 필요한 이후 작업들의 선행 조건
      2) init_db  — 테이블 생성/마이그레이션 (스케줄러가 DB 접근 전에 완료돼야 함)
      3) start_scheduler — 위 두 단계가 완료된 후 잡 등록
    """
    from app.services.file_generator import _bdq_login
    _bdq_login()        # BDQ_USER / BDQ_PASS 로 bigdataquery 세션 활성화
    init_db()           # SQLite 테이블 생성 + 누락 컬럼 마이그레이션
    start_scheduler()   # 매일 12시 배포 잡 + 5분 헬스체크 잡 등록

    yield               # 이 지점부터 실제 HTTP 요청을 처리

    stop_scheduler()    # 앱 종료 신호(Ctrl+C 등) 수신 시 스케줄러 정리


# ── FastAPI 앱 인스턴스 생성 ─────────────────────────────────────
app = FastAPI(title="설비 배포 대시보드", lifespan=lifespan)

# /static/... 요청을 프로젝트 루트의 static/ 폴더에서 파일로 응답
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 HTML 템플릿 엔진 — app/templates/ 폴더를 읽음
templates = Jinja2Templates(directory="app/templates")

# ── 라우터 등록 ──────────────────────────────────────────────────
app.include_router(equipment.router)       # /equipment, /api/equipment/*
app.include_router(deploy.router)          # /api/deploy/*
app.include_router(logs.router)            # /logs, /api/logs/*
app.include_router(files.router)           # /api/files/*, /api/test/*
app.include_router(bdq.router)             # /bdq, /api/bdq/*
app.include_router(priority.router)        # /priority, /api/priority/*


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    """메인 대시보드 페이지를 반환한다."""
    return templates.TemplateResponse("dashboard.html", {"request": request, "active_page": "dashboard"})


@app.get("/api/scheduler/status")
def scheduler_status():
    """현재 스케줄러 실행 여부와 다음 실행 예정 시각을 반환한다."""
    return get_scheduler_status()
