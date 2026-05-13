import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_LIGHTWEIGHT_MIGRATIONS = {
    "equipment": [
        ("last_ping_at",      "DATETIME"),
        ("last_ping_status",  "VARCHAR(20) NOT NULL DEFAULT 'unknown'"),
        ("last_ping_message", "TEXT NOT NULL DEFAULT ''"),
        ("last_ping_ms",      "INTEGER"),
    ],
}


def _apply_lightweight_migrations() -> None:
    """SQLite에서 누락된 컬럼만 ALTER TABLE 로 추가."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, columns in _LIGHTWEIGHT_MIGRATIONS.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for col_name, col_def in columns:
                if col_name in present:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))
                logger.info(f"마이그레이션: {table}.{col_name} 컬럼 추가")


def init_db():
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()
