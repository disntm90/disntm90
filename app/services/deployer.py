"""
deployer.py — 생성된 XML 파일을 설비 PC로 FTP/SFTP 전송

배포 경로는 OUTPUT_FILES 에 하드코딩되어 있어 변경 불가이다.
각 설비(Equipment)에 대해 두 파일(YieldConvDef, RejectMapFile)을 순서대로 전송한다.
"""

import ftplib
import logging
from pathlib import Path

from app.database import SessionLocal
from app.models import Equipment, DeployLog
from app.services.file_generator import OUTPUT_FILES as DEPLOY_FILES  # 파일 목록 단일 소스
from config import GENERATED_DIR

logger = logging.getLogger(__name__)


def _deploy_via_ftp(eq: Equipment, local_file: Path, remote_path: str) -> None:
    """
    표준 FTP 프로토콜로 파일 1개를 전송한다.

    with ftplib.FTP() as ftp: 구문으로 컨텍스트 매니저를 사용해
    예외 발생 시에도 자동으로 연결이 닫힌다.
    """
    with ftplib.FTP() as ftp:
        ftp.connect(eq.ip, eq.port, timeout=30)  # TCP 연결 (30초 타임아웃)
        ftp.login(eq.ftp_user, eq.ftp_pass)       # FTP 인증
        ftp.cwd(remote_path)                       # 원격 디렉토리 이동
        with open(local_file, "rb") as f:
            # STOR 명령: 파일명을 유지한 채 바이너리 스트림으로 업로드
            ftp.storbinary(f"STOR {local_file.name}", f)


def _deploy_via_sftp(eq: Equipment, local_file: Path, remote_path: str) -> None:
    """
    SFTP(SSH File Transfer Protocol) 로 파일 1개를 전송한다.

    paramiko 라이브러리를 사용한다. (pip install paramiko)
    transport와 sftp 객체를 finally 블록에서 반드시 닫아 연결 누수를 방지한다.
    """
    import paramiko
    transport = paramiko.Transport((eq.ip, eq.port))  # SSH 트랜스포트 레이어
    sftp = None
    try:
        transport.connect(username=eq.ftp_user, password=eq.ftp_pass)  # SSH 인증
        sftp = paramiko.SFTPClient.from_transport(transport)            # SFTP 채널 생성
        # 원격 경로 끝의 / 를 정규화한 뒤 파일명을 붙여 전체 경로 구성
        sftp.put(str(local_file), f"{remote_path.rstrip('/')}/{local_file.name}")
    finally:
        if sftp:
            sftp.close()       # SFTP 채널 해제
        transport.close()      # SSH 연결 해제


def deploy_to_equipment(eq: Equipment, triggered_by: str = "manual") -> list[dict]:
    """
    단일 설비에 YieldConvDef.xml 과 RejectMapFile.xml 을 배포한다.

    각 파일마다:
      - 로컬에 파일이 없으면 → failed 기록
      - 전송 성공 → success 기록
      - 전송 실패 → failed 기록 (다음 파일은 계속 시도)

    반환: 각 파일별 결과 딕셔너리 리스트
    """
    db = SessionLocal()
    results = []

    try:
        for file_type, filename, remote_path in DEPLOY_FILES:
            local_file = GENERATED_DIR / filename

            # 생성된 파일이 없으면 배포 불가
            if not local_file.exists():
                db.add(DeployLog(
                    equipment_id = eq.id,
                    file_type    = file_type,
                    status       = "failed",
                    message      = f"생성된 파일이 없습니다: {local_file}",
                    triggered_by = triggered_by,
                ))
                results.append({"equipment": eq.name, "file_type": file_type, "status": "failed"})
                continue   # 이 파일은 건너뛰고 다음 파일로

            try:
                # 설비 설정에 따라 프로토콜 선택
                if eq.use_sftp:
                    _deploy_via_sftp(eq, local_file, remote_path)
                else:
                    _deploy_via_ftp(eq, local_file, remote_path)

                db.add(DeployLog(
                    equipment_id = eq.id,
                    file_type    = file_type,
                    status       = "success",
                    message      = f"{filename} → {eq.ip}:{remote_path} 배포 완료",
                    triggered_by = triggered_by,
                ))
                results.append({"equipment": eq.name, "file_type": file_type, "status": "success"})
                logger.info(f"배포 완료: {eq.name} ({eq.ip}:{remote_path}) ← {filename}")

            except Exception as exc:
                db.add(DeployLog(
                    equipment_id = eq.id,
                    file_type    = file_type,
                    status       = "failed",
                    message      = str(exc),
                    triggered_by = triggered_by,
                ))
                results.append({"equipment": eq.name, "file_type": file_type,
                                 "status": "failed", "error": str(exc)})
                logger.error(f"배포 실패: {eq.name} ({eq.ip}) ← {filename}: {exc}")

        db.commit()   # 모든 파일 처리 완료 후 한 번에 커밋

    finally:
        db.close()

    return results


def run_full_deploy(equipment_list: list[Equipment], triggered_by: str = "scheduler") -> None:
    """
    전체 설비에 대한 전체 배포 워크플로우.

    단계:
      1. generate_all_files() 로 XML 파일 생성
      2. 생성 실패 시 → 배포 중단 (오래된 파일을 실수로 배포하지 않기 위함)
      3. 성공 시 → 모든 활성 설비에 순서대로 배포
    """
    from app.services.file_generator import generate_all_files

    logger.info(f"전체 배포 시작: {len(equipment_list)}개 설비 ({triggered_by})")

    generate_results = generate_all_files(triggered_by)
    gen_failed = [r for r in generate_results if r["status"] == "failed"]
    if gen_failed:
        # 파일 생성이 하나라도 실패하면 전체 배포를 중단한다.
        # 오래된 파일을 배포하는 것보다 배포하지 않는 게 더 안전하기 때문.
        logger.error(f"파일 생성 실패로 배포를 중단합니다: {gen_failed}")
        return

    for eq in equipment_list:
        deploy_to_equipment(eq, triggered_by)   # 설비마다 순차 배포

    logger.info("전체 배포 완료")
