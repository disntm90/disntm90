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
    _bdq_login,
)

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_PREVIEW_LINES = 200


def _safe_path(filename: str) -> Path:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="유효하지 않은 파일명입니다.")
    path = GENERATED_DIR / filename
    if not path.resolve().is_relative_to(GENERATED_DIR.resolve()):
        raise HTTPException(status_code=400, detail="유효하지 않은 파일명입니다.")
    return path


@router.get("/api/files/generated")
def list_generated_files():
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for p in sorted(GENERATED_DIR.iterdir()):
        if p.is_file():
            stat = p.stat()
            files.append({
                "name": p.name,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
    return {"files": files}


@router.get("/api/files/generated/{filename}")
def preview_generated_file(filename: str):
    path = _safe_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 읽기 오류: {e}")
    truncated = len(lines) > MAX_PREVIEW_LINES
    return {
        "filename": filename,
        "content": "\n".join(lines[:MAX_PREVIEW_LINES]),
        "truncated": truncated,
        "total_lines": len(lines),
    }


@router.get("/api/files/download/{filename}")
def download_generated_file(filename: str):
    path = _safe_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(str(path), filename=filename, media_type="application/octet-stream")


@router.post("/api/test/db-check")
def test_db_check():
    """로그인 → 실제 운영 쿼리(LIMIT 1)로 DB 연결 검증."""
    try:
        import bigdataquery as bdq
    except ImportError:
        return {"success": False, "message": "bigdataquery 패키지 없음"}

    if not _bdq_login():
        return {"success": False, "message": "bigdataquery 로그인 실패 (BDQ_USER/BDQ_PASS 확인)"}

    try:
        df = bdq.getData(param="""
            SELECT code_type, code_id
            FROM mos_tsp_smi.gpm_tp_be_mng_sbl_scrap_code
            WHERE vendor_name = 'ICOS'
            LIMIT 1
        """)
        return {"success": True, "message": f"DB 연결 성공 (조회 컬럼: {list(df.columns)})"}
    except Exception as e:
        logger.exception("DB 연결 테스트 실패")
        return {"success": False, "message": f"DB 연결 실패: {e}"}


class TestGenerateRequest(BaseModel):
    file_type: str = "ALL"


@router.post("/api/test/generate")
def test_generate(req: TestGenerateRequest):
    ft = req.file_type.upper()
    try:
        if ft == "YIELDCONVDEF":
            result = generate_yield_condef(triggered_by="test")
            results = [result]
        elif ft == "REJECTMAPFILE":
            result = generate_reject_mapfile(triggered_by="test")
            results = [result]
        else:
            results = generate_all_files(triggered_by="test")
    except Exception as e:
        logger.exception("test_generate 실패")
        return {"results": [], "success": False, "message": str(e)}

    success = all(r.get("status") == "success" for r in results)
    return {"results": results, "success": success}
