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


def _ftp_cwd(ftp: ftplib.FTP, path: str) -> None:
    """
    FTP 원격 디렉토리로 이동한다.

    Windows FTP 서버는 'C:/Icos' 형식 또는 '/C:/Icos' 형식 모두 가능하지만
    서버 구현마다 다르므로 두 형식을 순서대로 시도한다.
    디렉토리가 없으면 MKD로 생성한다.
    """
    paths_to_try = [path]
    # 슬래시로 시작하지 않으면 앞에 / 를 붙인 버전도 시도
    if not path.startswith("/"):
        paths_to_try.append("/" + path)

    last_err = None
    for p in paths_to_try:
        try:
            ftp.cwd(p)
            logger.debug(f"FTP CWD 성공: {p!r}")
            return
        except ftplib.error_perm as e:
            last_err = e
            logger.debug(f"FTP CWD 실패 ({p!r}): {e}")

    # 두 형식 모두 실패하면 디렉토리 생성 후 재시도
    logger.warning(f"원격 디렉토리 없음, 생성 시도: {path!r}")
    try:
        ftp.mkd(path)
        ftp.cwd(path)
        return
    except Exception as e:
        raise ftplib.error_perm(
            f"디렉토리 이동 실패 ({path!r}): {last_err} / 생성도 실패: {e}"
        )


def _deploy_via_ftp(eq: Equipment, local_file: Path, remote_path: str) -> None:
    """
    표준 FTP 프로토콜로 파일 1개를 전송한다.

    - 패시브 모드 활성화: 방화벽 환경에서 데이터 채널을 클라이언트가 열어 NAT/방화벽 통과
    - STOR 명령은 기존 파일이 있으면 자동으로 덮어쓰기한다
    """
    with ftplib.FTP() as ftp:
        ftp.connect(eq.ip, eq.port, timeout=30)  # TCP 연결
        ftp.login(eq.ftp_user, eq.ftp_pass)       # FTP 인증
        ftp.set_pasv(True)                         # 패시브 모드 (방화벽 환경 필수)
        _ftp_cwd(ftp, remote_path)                 # 원격 디렉토리 이동
        with open(local_file, "rb") as f:
            # STOR: 기존 파일이 있으면 덮어쓰기, 없으면 신규 생성
            ftp.storbinary(f"STOR {local_file.name}", f)
        logger.debug(f"FTP STOR 완료: {local_file.name} → {remote_path}")


def _deploy_via_sftp(eq: Equipment, local_file: Path, remote_path: str) -> None:
    """
    SFTP(SSH File Transfer Protocol) 로 파일 1개를 전송한다.

    paramiko 라이브러리를 사용한다. (pip install paramiko)
    transport와 sftp 객체를 finally 블록에서 반드시 닫아 연결 누수를 방지한다.
    """
    import paramiko
    transport = paramiko.Transport((eq.ip, eq.port))
    sftp = None
    try:
        transport.connect(username=eq.ftp_user, password=eq.ftp_pass)
        sftp = paramiko.SFTPClient.from_transport(transport)
        remote_file = f"{remote_path.rstrip('/')}/{local_file.name}"
        # put()은 기존 파일이 있으면 자동 덮어쓰기
        sftp.put(str(local_file), remote_file)
        logger.debug(f"SFTP PUT 완료: {local_file.name} → {remote_file}")
    finally:
        if sftp:
            sftp.close()
        transport.close()


def deploy_to_equipment(eq: Equipment, triggered_by: str = "manual") -> list[dict]:
    """
    단일 설비에 YieldConvDef.xml 과 RejectMapFile.xml 을 배포한다.

    각 파일마다:
      - 로컬에 파일이 없으면 → failed 기록
      - 전송 성공 → success 기록
      - 전송 실패 → failed 기록 + 상세 오류 로그 (다음 파일은 계속 시도)

    반환: 각 파일별 결과 딕셔너리 리스트
    """
    db = SessionLocal()
    results = []

    try:
        for file_type, filename, remote_path in DEPLOY_FILES:
            local_file = GENERATED_DIR / filename

            # 생성된 파일이 없으면 배포 불가
            if not local_file.exists():
                msg = f"생성된 파일이 없습니다: {local_file}"
                logger.error(msg)
                db.add(DeployLog(
                    equipment_id = eq.id,
                    file_type    = file_type,
                    status       = "failed",
                    message      = msg,
                    triggered_by = triggered_by,
                ))
                results.append({"equipment": eq.name, "file_type": file_type, "status": "failed"})
                continue

            try:
                if eq.use_sftp:
                    _deploy_via_sftp(eq, local_file, remote_path)
                else:
                    _deploy_via_ftp(eq, local_file, remote_path)

                msg = f"{filename} → {eq.ip}:{remote_path} 배포 완료"
                db.add(DeployLog(
                    equipment_id = eq.id,
                    file_type    = file_type,
                    status       = "success",
                    message      = msg,
                    triggered_by = triggered_by,
                ))
                results.append({"equipment": eq.name, "file_type": file_type, "status": "success"})
                logger.info(f"배포 완료: {eq.name} ({eq.ip}:{remote_path}) ← {filename}")

            except Exception as exc:
                # 오류 타입과 메시지를 모두 기록해 원인 파악이 쉽도록
                msg = f"[{type(exc).__name__}] {exc}"
                logger.error(f"배포 실패: {eq.name} ({eq.ip}) ← {filename}: {msg}")
                db.add(DeployLog(
                    equipment_id = eq.id,
                    file_type    = file_type,
                    status       = "failed",
                    message      = msg,
                    triggered_by = triggered_by,
                ))
                results.append({"equipment": eq.name, "file_type": file_type,
                                 "status": "failed", "error": msg})

        db.commit()

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
        logger.error(f"파일 생성 실패로 배포를 중단합니다: {gen_failed}")
        return

    for eq in equipment_list:
        deploy_to_equipment(eq, triggered_by)

    logger.info("전체 배포 완료")
