import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

DATABASE_URL = f"sqlite:///{BASE_DIR}/data/dashboard.db"

GENERATED_DIR = BASE_DIR / "generated_files"
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "12"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))

HEALTH_CHECK_INTERVAL_MIN = int(os.getenv("HEALTH_CHECK_INTERVAL_MIN", "5"))

UPSTREAM_HOST = os.getenv("UPSTREAM_HOST", "")
UPSTREAM_PORT = int(os.getenv("UPSTREAM_PORT", "21"))
UPSTREAM_USER = os.getenv("UPSTREAM_USER", "")
UPSTREAM_PASS = os.getenv("UPSTREAM_PASS", "")
UPSTREAM_PATH = os.getenv("UPSTREAM_PATH", "/")

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
