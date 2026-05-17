"""
health_check.py — 설비 FTP/SFTP 연결 상태 모니터링

동작 방식:
  - TCP ping: 소켓 연결만 시도 (빠름, 주기적 자동 점검에 사용)
  - FTP/SFTP 로그인: 프로토콜 수준의 인증까지 확인 (느림, 수동 테스트에 사용)
  - ThreadPoolExecutor 로 여러 설비를 동시에 점검해 총 소요 시간을 단축

점검 결과는 Equipment.last_ping_* 컬럼에 저장된다.
"""

import ftplib
import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed  # 병렬 실행
from datetime import datetime
from typing import Iterable

from app.database import SessionLocal
from app.models import Equipment

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 5   # 연결 시도 최대 대기 시간 (초)
MAX_WORKERS = 8       # 동시에 점검할 최대 설비 수


def _check_ftp(eq: Equipment) -> tuple[bool, str]:
    """FTP 프로토콜 로그인까지 확인. 성공 여부와 메시지를 반환한다."""
    try:
        with ftplib.FTP() as ftp:
            ftp.connect(eq.ip, eq.port, timeout=CONNECT_TIMEOUT)
            if eq.ftp_user:
                ftp.login(eq.ftp_user, eq.ftp_pass)
            else:
                ftp.login()              # 익명 로그인
            ftp.voidcmd("NOOP")          # 서버가 살아있는지 ping 명령 전송
        return True, "FTP 연결 정상"
    except Exception as exc:
        return False, f"FTP 실패: {exc}"


def _check_sftp(eq: Equipment) -> tuple[bool, str]:
    """SFTP 프로토콜 로그인까지 확인. paramiko가 없으면 즉시 실패 반환."""
    try:
        import paramiko
    except ImportError:
        return False, "paramiko 패키지 없음"

    transport = None
    try:
        transport = paramiko.Transport((eq.ip, eq.port))
        transport.banner_timeout = CONNECT_TIMEOUT   # SSH 배너 수신 대기 시간
        transport.connect(username=eq.ftp_user, password=eq.ftp_pass)
        return True, "SFTP 연결 정상"
    except Exception as exc:
        return False, f"SFTP 실패: {exc}"
    finally:
        if transport:
            transport.close()    # 인증 성공/실패 무관하게 연결 해제


def _check_tcp(eq: Equipment) -> tuple[bool, str]:
    """
    TCP 소켓 연결만 확인한다. (FTP 인증 없이 포트 열림 여부만 체크)
    빠른 주기 점검에 적합하다.
    """
    try:
        with socket.create_connection((eq.ip, eq.port), timeout=CONNECT_TIMEOUT):
            return True, f"TCP {eq.ip}:{eq.port} 응답 있음"
    except Exception as exc:
        return False, f"TCP 실패: {exc}"


def check_one(eq: Equipment, *, protocol_login: bool = True) -> dict:
    """
    단일 설비를 점검하고 결과 딕셔너리를 반환한다.

    protocol_login=True  → FTP/SFTP 로그인까지 확인 (수동 테스트용)
    protocol_login=False → TCP 연결만 확인 (주기적 자동 점검용)

    elapsed_ms: 점검에 걸린 시간(밀리초)
    """
    started = time.monotonic()  # 단조 시계 — 시스템 시간 변경에 영향 받지 않음

    if not protocol_login:
        ok, msg = _check_tcp(eq)
    elif eq.use_sftp:
        ok, msg = _check_sftp(eq)
    else:
        ok, msg = _check_ftp(eq)

    elapsed_ms = int((time.monotonic() - started) * 1000)  # 초 → 밀리초 변환

    return {
        "equipment_id": eq.id,
        "name":         eq.name,
        "ip":           eq.ip,
        "status":       "ok" if ok else "failed",
        "message":      msg,
        "elapsed_ms":   elapsed_ms,
    }


def _persist(eq_id: int, result: dict) -> None:
    """
    점검 결과를 Equipment.last_ping_* 컬럼에 저장한다.
    check_all 내부에서 쓰레드별로 호출되므로, 별도 DB 세션을 생성한다.
    """
    db = SessionLocal()
    try:
        eq = db.query(Equipment).filter(Equipment.id == eq_id).first()
        if not eq:
            return
        eq.last_ping_at      = datetime.now()
        eq.last_ping_status  = result["status"]
        eq.last_ping_message = result["message"]
        eq.last_ping_ms      = result["elapsed_ms"]
        db.commit()
    finally:
        db.close()


def check_equipment(eq_id: int, *, protocol_login: bool = True) -> dict:
    """
    설비 ID 를 받아 점검 후 결과를 DB에 저장하고 반환한다.
    API 엔드포인트 (POST /api/equipment/{id}/test-connection) 에서 호출된다.
    """
    db = SessionLocal()
    try:
        eq = db.query(Equipment).filter(Equipment.id == eq_id).first()
        if not eq:
            return {"status": "failed", "message": "설비를 찾을 수 없습니다."}
        result = check_one(eq, protocol_login=protocol_login)
    finally:
        db.close()

    _persist(eq_id, result)   # 결과를 DB에 반영
    return result


def check_all(*, only_active: bool = True, protocol_login: bool = False) -> list[dict]:
    """
    활성 설비 전체를 ThreadPoolExecutor 로 병렬 점검한다.

    only_active=True  → is_active=True 인 설비만
    protocol_login=False → TCP만 (빠른 주기 점검에서 사용)
    protocol_login=True  → FTP/SFTP 로그인까지 (수동 전체 테스트에서 사용)

    스레드 간 DB 세션 공유를 피하기 위해, DB에서 필요한 값만 읽고
    Equipment 객체 대신 튜플(snapshot)로 스레드에 전달한다.
    """
    db = SessionLocal()
    try:
        q = db.query(Equipment)
        if only_active:
            q = q.filter(Equipment.is_active == True)
        equipment = q.all()
        # 스레드에 전달할 최소 데이터만 추출 (ORM 객체는 스레드 안전하지 않음)
        snapshots = [
            (e.id, e.name, e.ip, e.port, e.ftp_user, e.ftp_pass, e.use_sftp)
            for e in equipment
        ]
    finally:
        db.close()

    if not snapshots:
        return []

    def _task(snapshot):
        """각 스레드에서 실행되는 함수: 임시 Equipment 객체 생성 후 점검."""
        eq = Equipment(
            id       = snapshot[0],
            name     = snapshot[1],
            ip       = snapshot[2],
            port     = snapshot[3],
            ftp_user = snapshot[4],
            ftp_pass = snapshot[5],
            use_sftp = snapshot[6],
        )
        result = check_one(eq, protocol_login=protocol_login)
        _persist(snapshot[0], result)   # 각 스레드에서 독립적으로 DB 저장
        return result

    results: list[dict] = []
    # MAX_WORKERS 개의 스레드를 풀로 관리해 병렬 실행
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(_task, s) for s in snapshots]
        for fut in as_completed(futures):   # 완료된 순서대로 결과 수집
            results.append(fut.result())

    ok = sum(1 for r in results if r["status"] == "ok")
    logger.info(f"헬스체크 완료: {ok}/{len(results)} 성공")
    return results
