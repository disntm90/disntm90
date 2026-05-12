"""FTP/SFTP를 사용하여 생성된 파일을 각 설비로 배포합니다."""

import ftplib
import logging
from pathlib import Path

from app.database import SessionLocal
from app.models import Equipment, DeployLog
from config import GENERATED_DIR

logger = logging.getLogger(__name__)

# file_generator.py와 동기화: 생성되는 파일 목록
DEPLOY_FILES = [
    ("X", "YieldConvDef.xml"),
    ("Y", "RejectCodeMap.xml"),
]


def _deploy_via_ftp(eq: Equipment, local_file: Path) -> None:
    with ftplib.FTP() as ftp:
        ftp.connect(eq.ip, eq.port, timeout=30)
        ftp.login(eq.ftp_user, eq.ftp_pass)
        ftp.cwd(eq.ftp_path)
        with open(local_file, "rb") as f:
            ftp.storbinary(f"STOR {local_file.name}", f)


def _deploy_via_sftp(eq: Equipment, local_file: Path) -> None:
    import paramiko
    transport = paramiko.Transport((eq.ip, eq.port))
    sftp = None
    try:
        transport.connect(username=eq.ftp_user, password=eq.ftp_pass)
        sftp = paramiko.SFTPClient.from_transport(transport)
        remote_path = f"{eq.ftp_path.rstrip('/')}/{local_file.name}"
        sftp.put(str(local_file), remote_path)
    finally:
        if sftp:
            sftp.close()
        transport.close()


def deploy_to_equipment(eq: Equipment, triggered_by: str = "manual") -> list[dict]:
    """단일 설비에 X, Y 파일을 모두 배포합니다."""
    db = SessionLocal()
    results = []

    try:
        for file_type, filename in DEPLOY_FILES:
            local_file = GENERATED_DIR / filename

            if not local_file.exists():
                log = DeployLog(
                    equipment_id=eq.id,
                    file_type=file_type,
                    status="failed",
                    message=f"생성된 파일이 없습니다: {local_file}",
                    triggered_by=triggered_by,
                )
                db.add(log)
                results.append({"equipment": eq.name, "file_type": file_type, "status": "failed"})
                continue

            try:
                if eq.use_sftp:
                    _deploy_via_sftp(eq, local_file)
                else:
                    _deploy_via_ftp(eq, local_file)

                log = DeployLog(
                    equipment_id=eq.id,
                    file_type=file_type,
                    status="success",
                    message=f"{filename} → {eq.ip}:{eq.ftp_path} 배포 완료",
                    triggered_by=triggered_by,
                )
                db.add(log)
                results.append({"equipment": eq.name, "file_type": file_type, "status": "success"})
                logger.info(f"배포 완료: {eq.name} ({eq.ip}) ← {filename}")

            except Exception as exc:
                log = DeployLog(
                    equipment_id=eq.id,
                    file_type=file_type,
                    status="failed",
                    message=str(exc),
                    triggered_by=triggered_by,
                )
                db.add(log)
                results.append({"equipment": eq.name, "file_type": file_type, "status": "failed", "error": str(exc)})
                logger.error(f"배포 실패: {eq.name} ({eq.ip}) ← {filename}: {exc}")

        db.commit()

    finally:
        db.close()

    return results


def run_full_deploy(equipment_list: list[Equipment], triggered_by: str = "scheduler") -> None:
    """전체 설비에 대해 파일 생성 → 배포를 순서대로 실행합니다."""
    from app.services.file_generator import generate_all_files

    logger.info(f"전체 배포 시작: {len(equipment_list)}개 설비 ({triggered_by})")

    generate_results = generate_all_files(triggered_by)
    gen_failed = [r for r in generate_results if r["status"] == "failed"]
    if gen_failed:
        logger.error(f"파일 생성 실패로 배포를 중단합니다: {gen_failed}")
        return

    for eq in equipment_list:
        deploy_to_equipment(eq, triggered_by)

    logger.info("전체 배포 완료")
