"""
routers/files.py — 생성 파일 조회/다운로드 및 테스트 API

URL 목록:
  GET  /api/files/generated             → 생성된 파일 목록
  GET  /api/files/generated/{filename}  → 파일 내용 미리보기 (최대 200줄)
  GET  /api/files/download/{filename}   → 파일 다운로드
  POST /api/test/db-check               → DB 연결 테스트
  POST /api/test/generate               → 파일 생성 테스트 (동기, 결과 즉시 반환)
"""
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import GENERATED_DIR
from app.services.file_generator import (
    generate_all_files,
    generate_yield_condef,
    generate_reject_mapfile,
)

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_PREVIEW_LINES = 200  # 미리보기 최대 줄 수 (너무 크면 브라우저가 느려짐)


def _safe_path(filename: str) -> Path:
    """
    경로 순회 공격(path traversal)을 방어하는 파일 경로 검증.

    '/', '\\', '..' 가 포함된 파일명을 거부하고,
    최종 경로가 GENERATED_DIR 안에 있는지 확인한다.
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="유효하지 않은 파일명입니다.")
    path = GENERATED_DIR / filename
    # resolve()로 심볼릭 링크와 .. 를 모두 해석한 절대 경로를 비교
    if not path.resolve().is_relative_to(GENERATED_DIR.resolve()):
        raise HTTPException(status_code=400, detail="유효하지 않은 파일명입니다.")
    return path


@router.get("/api/files/generated")
def list_generated_files():
    """GENERATED_DIR 안의 파일 목록을 이름순으로 반환한다."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for p in sorted(GENERATED_DIR.iterdir()):
        if p.is_file():
            stat = p.stat()
            files.append({
                "name":        p.name,
                "size":        stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
    return {"files": files}


@router.get("/api/files/generated/{filename}")
def preview_generated_file(filename: str):
    """
    파일 내용을 텍스트로 반환한다 (최대 200줄).

    truncated=True 이면 클라이언트에서 "이하 생략" 메시지를 표시한다.
    """
    path = _safe_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    try:
        # errors="replace" : 읽을 수 없는 문자는 ? 로 대체 (인코딩 오류로 중단되지 않음)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 읽기 오류: {e}")

    truncated = len(lines) > MAX_PREVIEW_LINES
    return {
        "filename":    filename,
        "content":     "\n".join(lines[:MAX_PREVIEW_LINES]),
        "truncated":   truncated,
        "total_lines": len(lines),
    }


@router.get("/api/files/download/{filename}")
def download_generated_file(filename: str):
    """파일을 바이너리 스트림으로 응답해 브라우저가 다운로드하게 한다."""
    path = _safe_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    # media_type="application/octet-stream" → 브라우저가 열지 않고 저장 대화상자를 띄움
    return FileResponse(str(path), filename=filename, media_type="application/octet-stream")


@router.post("/api/test/db-check")
def test_db_check():
    """
    실제 쿼리를 1건 실행해 DB 연결을 검증한다.
    로그인은 앱 시작 시 이미 완료된 상태이므로 여기서는 getData만 호출한다.
    """
    import os
    try:
        import bigdataquery as bdq
    except ImportError:
        return {"success": False, "message": "bigdataquery 패키지 없음"}

    user = os.getenv("BDQ_USER", "")
    try:
        df = bdq.getData(param="""
            SELECT code_type, code_id
            FROM mos_tsp_smi.gpm_tp_be_mng_sbl_scrap_code
            WHERE vendor_name = 'ICOS'
            LIMIT 1
        """, user_name=user)
        return {"success": True, "message": f"DB 연결 성공 (조회 컬럼: {list(df.columns)})"}
    except Exception as e:
        logger.exception("DB 연결 테스트 실패")
        return {"success": False, "message": f"DB 연결 실패: {e}"}


class TestGenerateRequest(BaseModel):
    """파일 생성 테스트 요청 바디"""
    file_type: str = "ALL"   # "YieldConvDef" / "RejectMapFile" / "ALL"


@router.post("/api/test/generate")
def test_generate(req: TestGenerateRequest):
    """
    파일을 동기적으로 생성하고 결과를 즉시 반환한다.
    (일반 /api/deploy/generate 는 백그라운드 실행이라 결과를 바로 알 수 없음)

    테스트 모드 화면의 생성 버튼에서 호출된다.
    """
    ft = req.file_type.upper()
    try:
        if ft == "YIELDCONVDEF":
            results = [generate_yield_condef(triggered_by="test")]
        elif ft == "REJECTMAPFILE":
            results = [generate_reject_mapfile(triggered_by="test")]
        else:
            results = generate_all_files(triggered_by="test")
    except Exception as e:
        logger.exception("test_generate 실패")
        return {"results": [], "success": False, "message": str(e)}

    # 모든 파일이 success일 때만 전체 성공으로 간주
    success = all(r.get("status") == "success" for r in results)
    return {"results": results, "success": success}
