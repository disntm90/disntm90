"""
routers/equipment.py — 설비 관리 API + 화면

URL 목록:
  GET  /equipment                            → 설비 관리 HTML 페이지
  GET  /api/equipment                        → 설비 목록 JSON
  POST /api/equipment                        → 설비 추가
  PUT  /api/equipment/{id}                   → 설비 수정
  DELETE /api/equipment/{id}                 → 설비 삭제 (HTMX 지원)
  POST /api/equipment/{id}/toggle            → 활성/비활성 전환 (HTMX 지원)
  POST /api/equipment/{id}/test-connection   → 단일 설비 연결 테스트 (HTMX 지원)
  POST /api/equipment/health-check           → 전체 설비 TCP 점검
  GET  /api/equipment/health-status          → 전체 헬스 상태 조회
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import Equipment
from app.services import health_check

router    = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ── HTMX 헬퍼 ────────────────────────────────────────────────────

def _is_htmx(request: Request) -> bool:
    """HTMX가 보내는 요청인지 판별한다. HX-Request 헤더 존재 여부로 확인."""
    return request.headers.get("HX-Request") == "true"


def _render_row(request: Request, eq: Equipment) -> HTMLResponse:
    """설비 행 partial 템플릿을 렌더링해 HTML 프래그먼트로 반환한다."""
    return templates.TemplateResponse("_equipment_row.html", {"request": request, "e": eq})


def _render_ping(request: Request, eq: Equipment) -> HTMLResponse:
    """연결 상태 셀 partial 템플릿을 렌더링해 HTML 프래그먼트로 반환한다."""
    return templates.TemplateResponse("_ping_cell.html", {"request": request, "e": eq})


# ── 직렬화 헬퍼 ──────────────────────────────────────────────────

def _serialize(e: Equipment) -> dict:
    """Equipment ORM 객체를 JSON 직렬화 가능한 딕셔너리로 변환한다."""
    return {
        "id":                e.id,
        "name":              e.name,
        "ip":                e.ip,
        "port":              e.port,
        "ftp_user":          e.ftp_user,
        "use_sftp":          e.use_sftp,
        "is_active":         e.is_active,
        "description":       e.description,
        "created_at":        e.created_at.strftime("%Y-%m-%d %H:%M"),
        # 헬스체크 결과 — last_ping_at이 None이면 "미점검" 상태
        "last_ping_at":      e.last_ping_at.strftime("%Y-%m-%d %H:%M:%S") if e.last_ping_at else None,
        "last_ping_status":  e.last_ping_status or "unknown",
        "last_ping_message": e.last_ping_message or "",
        "last_ping_ms":      e.last_ping_ms,
    }


# ── Pydantic 스키마 (요청 바디 검증) ─────────────────────────────

class EquipmentCreate(BaseModel):
    """설비 추가 시 클라이언트가 보내는 JSON 형식"""
    name:        str
    ip:          str
    port:        int  = 21
    ftp_user:    str  = ""
    ftp_pass:    str  = ""
    use_sftp:    bool = False
    description: str  = ""


class EquipmentUpdate(BaseModel):
    """설비 수정 시 클라이언트가 보내는 JSON 형식 (모든 필드 선택적)"""
    name:        str | None  = None
    ip:          str | None  = None
    port:        int | None  = None
    ftp_user:    str | None  = None
    ftp_pass:    str | None  = None
    use_sftp:    bool | None = None
    is_active:   bool | None = None
    description: str | None  = None


# ── 라우터 핸들러 ─────────────────────────────────────────────────

@router.get("/equipment", response_class=HTMLResponse)
def equipment_page(request: Request, db: Session = Depends(get_db)):
    """설비 관리 HTML 페이지를 렌더링한다. 설비 목록을 초기 데이터로 전달."""
    items = db.query(Equipment).order_by(Equipment.name).all()
    return templates.TemplateResponse(
        "equipment.html",
        {"request": request, "equipment_list": items, "active_page": "equipment"}
    )


@router.get("/api/equipment")
def list_equipment(db: Session = Depends(get_db)):
    """설비 전체 목록을 JSON으로 반환한다."""
    items = db.query(Equipment).order_by(Equipment.name).all()
    return [_serialize(e) for e in items]


@router.post("/api/equipment")
def create_equipment(data: EquipmentCreate, db: Session = Depends(get_db)):
    """새 설비를 등록한다. 동일 IP가 이미 있으면 400 오류를 반환한다."""
    existing = db.query(Equipment).filter(Equipment.ip == data.ip).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"IP {data.ip} 는 이미 등록되어 있습니다.")
    eq = Equipment(**data.model_dump())  # Pydantic 모델 → ORM 모델
    db.add(eq)
    db.commit()
    db.refresh(eq)   # DB가 생성한 id 등을 다시 읽어옴
    return {"id": eq.id, "message": f"설비 '{eq.name}' 이(가) 등록되었습니다."}


@router.put("/api/equipment/{equipment_id}")
def update_equipment(equipment_id: int, data: EquipmentUpdate, db: Session = Depends(get_db)):
    """설비 정보를 수정한다. 전달된 필드만 업데이트한다 (partial update)."""
    eq = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="설비를 찾을 수 없습니다.")
    # exclude_none=True: None인 필드는 건너뛰어 기존 값을 유지
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(eq, field, value)
    eq.updated_at = datetime.now()
    db.commit()
    return {"message": f"설비 '{eq.name}' 이(가) 수정되었습니다."}


@router.delete("/api/equipment/{equipment_id}")
def delete_equipment(equipment_id: int, request: Request, db: Session = Depends(get_db)):
    """
    설비를 삭제한다.
    HTMX 요청이면 빈 HTML(= 행 제거)을 반환하고, 일반 요청이면 JSON을 반환한다.
    """
    eq = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="설비를 찾을 수 없습니다.")
    name = eq.name
    db.delete(eq)
    db.commit()

    if _is_htmx(request):
        # hx-swap="outerHTML" 에 빈 응답을 보내면 해당 행이 제거됨
        return Response(content="", media_type="text/html")
    return {"message": f"설비 '{name}' 이(가) 삭제되었습니다."}


@router.post("/api/equipment/{equipment_id}/toggle")
def toggle_equipment(equipment_id: int, request: Request, db: Session = Depends(get_db)):
    """
    설비의 활성/비활성 상태를 반전한다.
    HTMX 요청이면 갱신된 행 HTML을, 일반 요청이면 JSON을 반환한다.
    """
    eq = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="설비를 찾을 수 없습니다.")
    eq.is_active  = not eq.is_active   # True ↔ False 반전
    eq.updated_at = datetime.now()
    db.commit()

    if _is_htmx(request):
        return _render_row(request, eq)  # 행 전체를 갱신된 상태로 교체
    status = "활성화" if eq.is_active else "비활성화"
    return {"message": f"설비 '{eq.name}' 이(가) {status}되었습니다.", "is_active": eq.is_active}


@router.post("/api/equipment/{equipment_id}/test-connection")
def test_equipment_connection(equipment_id: int, request: Request, db: Session = Depends(get_db)):
    """
    단일 설비에 FTP/SFTP 로그인까지 시도해 연결 상태를 갱신한다.
    HTMX 요청이면 연결 상태 셀 HTML을, 일반 요청이면 JSON을 반환한다.
    """
    result = health_check.check_equipment(equipment_id, protocol_login=True)
    if result.get("status") not in ("ok", "failed"):
        raise HTTPException(status_code=404, detail=result.get("message", "설비를 찾을 수 없습니다."))

    if _is_htmx(request):
        # DB에서 최신 ping 결과가 반영된 설비를 다시 읽어 셀 렌더링
        eq = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        return _render_ping(request, eq)
    return result


@router.post("/api/equipment/health-check")
def run_health_check():
    """활성 설비 전체에 TCP 점검을 실행하고 요약 결과를 반환한다."""
    results = health_check.check_all(only_active=True, protocol_login=False)
    summary = {
        "total":  len(results),
        "ok":     sum(1 for r in results if r["status"] == "ok"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
    }
    return {"results": results, "summary": summary}


@router.get("/api/equipment/health-status")
def health_status(db: Session = Depends(get_db)):
    """활성 설비의 최신 헬스체크 상태와 요약을 반환한다. 대시보드 헬스 카드에서 사용."""
    items    = db.query(Equipment).filter(Equipment.is_active == True).order_by(Equipment.name).all()
    statuses = [_serialize(e) for e in items]
    summary  = {
        "total":   len(statuses),
        "ok":      sum(1 for s in statuses if s["last_ping_status"] == "ok"),
        "failed":  sum(1 for s in statuses if s["last_ping_status"] == "failed"),
        "unknown": sum(1 for s in statuses if s["last_ping_status"] == "unknown"),
    }
    return {"equipment": statuses, "summary": summary}
