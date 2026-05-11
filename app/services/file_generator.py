"""
X, Y 파일 생성 서비스.
DB에 저장된 템플릿에서 파일을 생성하며,
상위 서버에서 다운로드한 기준 데이터를 변수로 치환합니다.

템플릿 변수 사용 예시:
  {{DATE}}       → 오늘 날짜 (YYYY-MM-DD)
  {{TIME}}       → 현재 시각 (HH:MM:SS)
  {{EQUIPMENT}}  → 설비명 (설비별 배포 시)
  {{ref:KEY}}    → 상위 서버 기준 데이터의 KEY 값
"""

import ftplib
import logging
from datetime import datetime
from pathlib import Path

from app.database import SessionLocal
from app.models import FileTemplate, GenerateLog
from config import (
    GENERATED_DIR,
    UPSTREAM_HOST,
    UPSTREAM_PORT,
    UPSTREAM_USER,
    UPSTREAM_PASS,
    UPSTREAM_PATH,
)

logger = logging.getLogger(__name__)


def _download_reference_data() -> dict:
    """상위 서버에서 기준 데이터를 다운로드하여 딕셔너리로 반환합니다."""
    if not UPSTREAM_HOST:
        logger.warning("상위 서버 설정이 없습니다. 빈 기준 데이터를 사용합니다.")
        return {}

    ref_data: dict = {}
    try:
        with ftplib.FTP() as ftp:
            ftp.connect(UPSTREAM_HOST, UPSTREAM_PORT, timeout=30)
            ftp.login(UPSTREAM_USER, UPSTREAM_PASS)
            ftp.cwd(UPSTREAM_PATH)

            filenames = ftp.nlst()
            for filename in filenames:
                lines: list[str] = []
                ftp.retrlines(f"RETR {filename}", lines.append)
                for line in lines:
                    if "=" in line:
                        key, _, value = line.partition("=")
                        ref_data[key.strip()] = value.strip()

        logger.info(f"상위 서버에서 기준 데이터 {len(ref_data)}개 항목을 다운로드했습니다.")
    except Exception as exc:
        logger.error(f"상위 서버 데이터 다운로드 실패: {exc}")

    return ref_data


def _apply_template(content: str, ref_data: dict, extra: dict | None = None) -> str:
    """템플릿 변수를 치환합니다."""
    now = datetime.now()
    variables = {
        "DATE": now.strftime("%Y-%m-%d"),
        "TIME": now.strftime("%H:%M:%S"),
        "DATETIME": now.strftime("%Y-%m-%d %H:%M:%S"),
        "YEAR": now.strftime("%Y"),
        "MONTH": now.strftime("%m"),
        "DAY": now.strftime("%d"),
    }
    if extra:
        variables.update(extra)

    result = content
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", value)

    for key, value in ref_data.items():
        result = result.replace(f"{{{{ref:{key}}}}}", value)

    return result


def generate_all_files(triggered_by: str = "scheduler") -> list[dict]:
    """모든 활성 템플릿에서 파일을 생성합니다."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    ref_data = _download_reference_data()
    db = SessionLocal()
    results = []

    try:
        templates = db.query(FileTemplate).filter(FileTemplate.is_active == True).all()

        for tmpl in templates:
            try:
                content = _apply_template(tmpl.content, ref_data)
                output_path = GENERATED_DIR / tmpl.filename
                output_path.write_text(content, encoding="utf-8")

                log = GenerateLog(
                    file_type=tmpl.file_type,
                    filename=tmpl.filename,
                    status="success",
                    message=f"파일 생성 완료: {output_path}",
                    triggered_by=triggered_by,
                )
                db.add(log)
                results.append({"file_type": tmpl.file_type, "filename": tmpl.filename, "status": "success"})
                logger.info(f"파일 생성 완료: {tmpl.filename}")

            except Exception as exc:
                log = GenerateLog(
                    file_type=tmpl.file_type,
                    filename=tmpl.filename,
                    status="failed",
                    message=str(exc),
                    triggered_by=triggered_by,
                )
                db.add(log)
                results.append({"file_type": tmpl.file_type, "filename": tmpl.filename, "status": "failed", "error": str(exc)})
                logger.error(f"파일 생성 실패 ({tmpl.filename}): {exc}")

        db.commit()

    finally:
        db.close()

    return results
