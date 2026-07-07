"""
routers/priority.py — YieldConvDef 출력 우선순위 관리 API + 화면

YieldConvDef.xml 의 <Yield> 태그 출력 순서를 대시보드에서 드래그&드롭으로
편집하고 SQLite(yield_priority 테이블)에 저장한다.
generate_yield_condef() 가 파일 생성 시 이 순서를 읽어 반영한다.

URL 목록:
  GET  /priority             → 우선순위 관리 HTML 페이지
  GET  /api/priority         → 저장된 순서 + 현재 BDQ code_type 병합 목록 (JSON)
  POST /api/priority/save    → 편집한 순서를 저장 (전체 교체)
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.database import SessionLocal
from app.models import YieldPriority
from app.services.file_generator import _fetch_scrap_data

logger    = logging.getLogger(__name__)
router    = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _group_rank(code_type: str) -> int:
    """
    접두사 그룹 정렬 순위 — generate_yield_condef()의 fallback 정렬과 동일.
    신규(미저장) code_type을 목록 맨 뒤에 붙일 때의 기본 순서로 사용한다.
    """
    for rank, prefix in enumerate(("BGA", "3D", "BBI", "TOPSMI"), start=1):
        if code_type.startswith(prefix):
            return rank
    return 5


def _current_bdq_code_types() -> tuple[list[str], str | None]:
    """
    현재 BDQ 조회 결과의 code_type 목록(대문자·중복제거, 원본 순서 유지)을 반환한다.
    조회 실패 시 ([], 오류메시지) 를 반환해 화면에서는 저장된 목록만 표시한다.
    """
    df = _fetch_scrap_data()
    if df is None:
        return [], "BDQ 조회 실패(로그인 실패 또는 데이터 없음). 저장된 목록만 표시합니다."

    seen: set = set()
    codes: list = []
    for ct in df["code_type"]:
        key = str(ct).strip().upper()
        if key and key not in seen:
            seen.add(key)
            codes.append(key)
    return codes, None


@router.get("/api/priority")
def get_priority():
    """
    저장된 우선순위(yield_priority 테이블)와 현재 BDQ code_type을 병합해 반환한다.

    - 저장된 순서를 먼저 배치(sort_order 오름차순)
    - BDQ에만 있는 신규 code_type은 접두사 그룹 + 이름 순으로 맨 뒤에 추가
    - 각 항목에 in_bdq(현재 조회에 존재), saved(DB 저장됨) 플래그 부여
    """
    db = SessionLocal()
    try:
        saved_rows = db.query(YieldPriority).order_by(YieldPriority.sort_order).all()
        saved_order = [r.code_type for r in saved_rows]
    finally:
        db.close()
    saved_set = set(saved_order)

    current, bdq_error = _current_bdq_code_types()
    current_set = set(current)

    # BDQ에만 있는 신규 항목(저장 안 됨) — 접두사 그룹 + 이름 순
    new_codes = sorted(
        (c for c in current if c not in saved_set),
        key=lambda c: (_group_rank(c), c),
    )

    rows = []
    for c in saved_order:
        rows.append({"code_type": c, "saved": True, "in_bdq": c in current_set})
    for c in new_codes:
        rows.append({"code_type": c, "saved": False, "in_bdq": True})

    missing = sum(1 for c in saved_order if c not in current_set)
    return {
        "rows": rows,
        "counts": {
            "total":   len(rows),
            "saved":   len(saved_order),
            "new":     len(new_codes),
            "missing": missing,   # 저장돼 있으나 현재 BDQ 조회엔 없는 항목 수
        },
        "bdq_error": bdq_error,
    }


class SaveOrderRequest(BaseModel):
    """우선순위 저장 요청 — code_type을 원하는 순서대로 나열한 배열."""
    order: list[str]


@router.post("/api/priority/save")
def save_priority(req: SaveOrderRequest):
    """
    편집한 순서를 yield_priority 테이블에 저장한다(전체 교체).

    - 정규화(대문자·공백제거) + 중복 제거(첫 등장 순서 유지)
    - 기존 행을 모두 삭제한 뒤 index를 sort_order로 하여 재삽입
    """
    seen: set = set()
    clean: list = []
    for c in req.order:
        key = str(c).strip().upper()
        if key and key not in seen:
            seen.add(key)
            clean.append(key)

    db = SessionLocal()
    try:
        db.query(YieldPriority).delete()   # 즉시 실행되는 벌크 삭제 (unique 충돌 방지)
        db.flush()
        for i, code in enumerate(clean):
            db.add(YieldPriority(code_type=code, sort_order=i))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("우선순위 저장 실패")
        raise HTTPException(status_code=500, detail=f"저장 실패: {exc}")
    finally:
        db.close()

    logger.info(f"YieldConvDef 우선순위 저장: {len(clean)}건")
    return {"success": True, "message": f"{len(clean)}건 우선순위를 저장했습니다.", "count": len(clean)}


@router.get("/priority", response_class=HTMLResponse)
def priority_page(request: Request):
    """우선순위 관리 HTML 페이지를 렌더링한다."""
    return templates.TemplateResponse(
        "priority.html",
        {"request": request, "active_page": "priority"},
    )
