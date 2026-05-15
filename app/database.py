"""
database.py — SQLAlchemy 데이터베이스 연결 및 초기화

SQLite 파일 기반 DB를 사용한다.
- engine  : DB 연결 객체 (실제 파일 접근 담당)
- Session : DB 작업 단위 (쿼리·커밋·롤백을 묶는 컨텍스트)
- Base    : 모든 ORM 모델이 상속하는 기반 클래스
"""
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import DATABASE_URL

logger = logging.getLogger(__name__)

# ── 엔진 생성 ───────────────────────────────────────────────────
# check_same_thread=False: SQLite 기본값은 단일 스레드만 허용인데,
# FastAPI는 멀티스레드 환경이므로 이 제한을 해제해야 한다.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# ── 세션 팩토리 ─────────────────────────────────────────────────
# autocommit=False : 변경사항은 db.commit() 을 명시적으로 호출해야 저장된다.
# autoflush=False  : commit 전 자동 flush를 막아 의도치 않은 쿼리를 방지한다.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── ORM 베이스 클래스 ────────────────────────────────────────────
class Base(DeclarativeBase):
    """모든 모델(Equipment, DeployLog …)이 이 클래스를 상속한다."""
    pass


def get_db():
    """
    FastAPI 의존성 주입용 DB 세션 제공 함수.

    라우터 함수의 인자에 `db: Session = Depends(get_db)` 로 선언하면
    요청마다 새 세션을 받고, 요청 종료 시 자동으로 세션이 닫힌다.
    """
    db = SessionLocal()
    try:
        yield db          # 요청 처리 중에는 세션을 빌려줌
    finally:
        db.close()        # 요청 완료(또는 예외) 시 반드시 세션을 반환


# ── 가벼운 마이그레이션 정의 ─────────────────────────────────────
# SQLite는 ORM create_all()로 기존 테이블에 컬럼을 추가하지 않는다.
# 따라서 '새 컬럼 목록'을 여기서 정의하고, 없는 컬럼만 ALTER TABLE로 추가한다.
_LIGHTWEIGHT_MIGRATIONS = {
    "equipment": [
        # (컬럼명, DDL 타입·기본값)
        ("last_ping_at",      "DATETIME"),                                 # 마지막 연결 점검 시각
        ("last_ping_status",  "VARCHAR(20) NOT NULL DEFAULT 'unknown'"),   # ok / failed / unknown
        ("last_ping_message", "TEXT NOT NULL DEFAULT ''"),                 # 점검 결과 메시지
        ("last_ping_ms",      "INTEGER"),                                  # 응답 시간(ms)
    ],
}


def _apply_lightweight_migrations() -> None:
    """
    누락된 컬럼이 있을 때만 ALTER TABLE로 추가하는 안전한 마이그레이션.

    이미 컬럼이 존재하면 아무 작업도 하지 않으므로,
    앱을 재시작해도 오류 없이 통과한다.
    """
    inspector = inspect(engine)          # 현재 DB 스키마 정보를 읽는 도구
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:         # 트랜잭션 시작 (블록 종료 시 자동 커밋)
        for table, columns in _LIGHTWEIGHT_MIGRATIONS.items():
            if table not in existing_tables:
                continue                 # 테이블 자체가 없으면 건너뜀 (이후 create_all이 생성)

            # 현재 테이블에 있는 컬럼 이름 목록
            present = {c["name"] for c in inspector.get_columns(table)}

            for col_name, col_def in columns:
                if col_name in present:
                    continue             # 이미 있는 컬럼은 건너뜀

                # 없는 컬럼만 추가
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))
                logger.info(f"마이그레이션: {table}.{col_name} 컬럼 추가")


def _seed_file_templates() -> None:
    """앱 최초 실행 시 RejectMapFile 기본 템플릿을 DB에 시드한다."""
    from app.models import FileTemplate
    from app.services.file_generator import STATIC_XML_TEMPLATE

    db = SessionLocal()
    try:
        existing = db.query(FileTemplate).filter(
            FileTemplate.file_type == "RejectMapFile"
        ).first()
        if existing:
            return
        db.add(FileTemplate(
            file_type="RejectMapFile",
            filename="RejectMapFile.xml",
            content=STATIC_XML_TEMPLATE,
            description="RejectMapFile 정적 XML 뼈대 템플릿 (자동 시드)",
            is_active=True,
            updated_by="system",
        ))
        db.commit()
        logger.info("FileTemplate 시드 완료: RejectMapFile")
    finally:
        db.close()


def init_db():
    """
    앱 시작 시 한 번 호출된다 (main.py lifespan).

    1. create_all : ORM 모델 기준으로 없는 테이블을 생성한다.
    2. 마이그레이션: 기존 테이블에 누락된 컬럼을 추가한다.
    3. 시드: FileTemplate 기본 데이터가 없으면 삽입한다.
    """
    from app import models  # noqa: F401 — 모델 클래스를 Base에 등록하기 위해 import
    Base.metadata.create_all(bind=engine)   # 정의된 테이블이 없으면 생성
    _apply_lightweight_migrations()          # 새 컬럼이 있으면 추가
    _seed_file_templates()                   # RejectMapFile 기본 템플릿 시드
