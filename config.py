"""
config.py — 앱 전역 설정

.env 파일에서 환경변수를 읽어 파이썬 상수로 노출한다.
다른 모듈은 이 파일만 import해서 설정값을 사용한다.
"""
import os
from pathlib import Path
from dotenv import load_dotenv  # .env 파일을 읽어 os.environ에 주입

# 프로젝트 루트 디렉토리 (.env, data/, generated_files/ 등이 위치)
load_dotenv()  # .env 파일을 실제로 읽는 시점 — import 순서상 여기서 한 번만 실행

BASE_DIR = Path(__file__).parent  # 이 파일(config.py)이 있는 디렉토리 = 프로젝트 루트

# ── 경로 설정 ──────────────────────────────────────────────────
DATABASE_URL = f"sqlite:///{BASE_DIR}/data/dashboard.db"  # SQLite DB 파일 경로
GENERATED_DIR = BASE_DIR / "generated_files"              # 생성된 XML 파일이 저장되는 폴더
DATA_DIR      = BASE_DIR / "data"                          # primecode.csv, static_xml_template.txt 등
LOG_DIR       = BASE_DIR / "logs"                          # app.log가 저장되는 폴더

# ── 스케줄 설정 ─────────────────────────────────────────────────
# 매일 이 시각에 파일 생성 → FTP 배포 잡이 자동 실행된다
SCHEDULE_HOUR   = int(os.getenv("SCHEDULE_HOUR",   "12"))  # 기본: 낮 12시
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))   # 기본: 0분

# 설비 FTP 연결 상태를 주기적으로 점검하는 간격 (분)
HEALTH_CHECK_INTERVAL_MIN = int(os.getenv("HEALTH_CHECK_INTERVAL_MIN", "5"))

# ── 레거시 UPSTREAM 설정 (현재 미사용) ──────────────────────────
UPSTREAM_HOST = os.getenv("UPSTREAM_HOST", "")
UPSTREAM_PORT = int(os.getenv("UPSTREAM_PORT", "21"))
UPSTREAM_USER = os.getenv("UPSTREAM_USER", "")
UPSTREAM_PASS = os.getenv("UPSTREAM_PASS", "")
UPSTREAM_PATH = os.getenv("UPSTREAM_PATH", "/")

# ── 보안 키 ─────────────────────────────────────────────────────
# 현재 직접 사용되지 않지만, 추후 세션 서명 등에 활용 가능
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
