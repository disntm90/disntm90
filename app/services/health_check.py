"""설비 FTP/SFTP 연결 상태 모니터링.

- TCP ping → 프로토콜 로그인까지 시도해 응답 시간을 측정한다.
- 결과는 Equipment.last_ping_* 컬럼에 저장.
"""

import ftplib
import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Iterable

from app.database import SessionLocal
from app.models import Equipment

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 5
MAX_WORKERS = 8


def _check_ftp(eq: Equipment) -> tuple[bool, str]:
    try:
        with ftplib.FTP() as ftp:
            ftp.connect(eq.ip, eq.port, timeout=CONNECT_TIMEOUT)
            if eq.ftp_user:
                ftp.login(eq.ftp_user, eq.ftp_pass)
            else:
                ftp.login()
            ftp.voidcmd("NOOP")
        return True, "FTP 연결 정상"
    except Exception as exc:
        return False, f"FTP 실패: {exc}"


def _check_sftp(eq: Equipment) -> tuple[bool, str]:
    try:
        import paramiko
    except ImportError:
        return False, "paramiko 패키지 없음"

    transport = None
    try:
        transport = paramiko.Transport((eq.ip, eq.port))
        transport.banner_timeout = CONNECT_TIMEOUT
        transport.connect(username=eq.ftp_user, password=eq.ftp_pass)
        return True, "SFTP 연결 정상"
    except Exception as exc:
        return False, f"SFTP 실패: {exc}"
    finally:
        if transport:
            transport.close()


def _check_tcp(eq: Equipment) -> tuple[bool, str]:
    try:
        with socket.create_connection((eq.ip, eq.port), timeout=CONNECT_TIMEOUT):
            return True, f"TCP {eq.ip}:{eq.port} 응답 있음"
    except Exception as exc:
        return False, f"TCP 실패: {exc}"


def check_one(eq: Equipment, *, protocol_login: bool = True) -> dict:
    """단일 설비 연결 점검. protocol_login=False면 TCP만."""
    started = time.monotonic()

    if not protocol_login:
        ok, msg = _check_tcp(eq)
    elif eq.use_sftp:
        ok, msg = _check_sftp(eq)
    else:
        ok, msg = _check_ftp(eq)

    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {
        "equipment_id": eq.id,
        "name": eq.name,
        "ip": eq.ip,
        "status": "ok" if ok else "failed",
        "message": msg,
        "elapsed_ms": elapsed_ms,
    }


def _persist(eq_id: int, result: dict) -> None:
    db = SessionLocal()
    try:
        eq = db.query(Equipment).filter(Equipment.id == eq_id).first()
        if not eq:
            return
        eq.last_ping_at = datetime.now()
        eq.last_ping_status = result["status"]
        eq.last_ping_message = result["message"]
        eq.last_ping_ms = result["elapsed_ms"]
        db.commit()
    finally:
        db.close()


def check_equipment(eq_id: int, *, protocol_login: bool = True) -> dict:
    db = SessionLocal()
    try:
        eq = db.query(Equipment).filter(Equipment.id == eq_id).first()
        if not eq:
            return {"status": "failed", "message": "설비를 찾을 수 없습니다."}
        result = check_one(eq, protocol_login=protocol_login)
    finally:
        db.close()

    _persist(eq_id, result)
    return result


def check_all(*, only_active: bool = True, protocol_login: bool = False) -> list[dict]:
    """전체(활성) 설비 동시 점검. 주기적 헬스체크는 TCP만(빠르게)."""
    db = SessionLocal()
    try:
        q = db.query(Equipment)
        if only_active:
            q = q.filter(Equipment.is_active == True)
        equipment = q.all()
        snapshots = [(e.id, e.name, e.ip, e.port, e.ftp_user, e.ftp_pass, e.use_sftp) for e in equipment]
    finally:
        db.close()

    if not snapshots:
        return []

    def _task(snapshot):
        eq = Equipment(
            id=snapshot[0], name=snapshot[1], ip=snapshot[2], port=snapshot[3],
            ftp_user=snapshot[4], ftp_pass=snapshot[5], use_sftp=snapshot[6],
        )
        result = check_one(eq, protocol_login=protocol_login)
        _persist(snapshot[0], result)
        return result

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(_task, s) for s in snapshots]
        for fut in as_completed(futures):
            results.append(fut.result())

    ok = sum(1 for r in results if r["status"] == "ok")
    logger.info(f"헬스체크 완료: {ok}/{len(results)} 성공")
    return results
