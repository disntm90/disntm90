"""
routers/bdq.py — BDQ 쿼리 데이터 확인 페이지

URL 목록:
  GET /bdq             → 쿼리 데이터 HTML 페이지
  GET /api/bdq/query   → BDQ 테이블 원본 데이터 + 요약 통계 (JSON)
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.file_generator import _fetch_scrap_data, _BDQ_TABLE

router    = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _classify_group(code_type: str) -> str:
    """code_type prefix로 그룹 분류 — generate_yield_condef()의 정렬 우선순위와 동일."""
    if code_type.startswith("BGA"):
        return "BGA"
    if code_type.startswith("3D"):
        return "3D"
    if code_type.startswith("BBI"):
        return "BBI"
    if code_type.startswith("TOPSMI"):
        return "TOPSMI"
    return "기타"


@router.get("/api/bdq/query")
def query_bdq_data():
    """
    BDQ 테이블 원본 데이터를 조회해 행 목록 + 그룹별 요약을 반환한다.
    매 호출마다 _fetch_scrap_data()가 BDQ 세션을 갱신하므로 최신 데이터를 받는다.
    """
    df = _fetch_scrap_data()
    if df is None:
        raise HTTPException(status_code=503, detail="BDQ 조회 실패: 로그인 실패 또는 데이터 없음")

    rows = [
        {"code_type": str(r.code_type), "code_id": str(r.code_id)}
        for r in df.itertuples(index=False)
    ]

    groups = {"BGA": 0, "3D": 0, "BBI": 0, "TOPSMI": 0, "기타": 0}
    for row in rows:
        groups[_classify_group(row["code_type"])] += 1

    return {
        "table":      _BDQ_TABLE,
        "queried_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rows":       rows,
        "summary":    {"total": len(rows), "groups": groups},
    }


@router.get("/bdq", response_class=HTMLResponse)
def bdq_page(request: Request):
    """쿼리 데이터 HTML 페이지를 렌더링한다."""
    return templates.TemplateResponse(
        "bdq.html",
        {"request": request, "active_page": "bdq"},
    )
