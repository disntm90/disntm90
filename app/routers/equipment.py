from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import Equipment
from app.services import health_check

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class EquipmentCreate(BaseModel):
    name: str
    ip: str
    port: int = 21
    ftp_user: str = ""
    ftp_pass: str = ""
    ftp_path: str = "/"
    use_sftp: bool = False
    description: str = ""


class EquipmentUpdate(BaseModel):
    name: str | None = None
    ip: str | None = None
    port: int | None = None
    ftp_user: str | None = None
    ftp_pass: str | None = None
    ftp_path: str | None = None
    use_sftp: bool | None = None
    is_active: bool | None = None
    description: str | None = None


@router.get("/equipment", response_class=HTMLResponse)
def equipment_page(request: Request, db: Session = Depends(get_db)):
    items = db.query(Equipment).order_by(Equipment.name).all()
    return templates.TemplateResponse("equipment.html", {"request": request, "equipment_list": items})


def _serialize(e: Equipment) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "ip": e.ip,
        "port": e.port,
        "ftp_user": e.ftp_user,
        "ftp_path": e.ftp_path,
        "use_sftp": e.use_sftp,
        "is_active": e.is_active,
        "description": e.description,
        "created_at": e.created_at.strftime("%Y-%m-%d %H:%M"),
        "last_ping_at": e.last_ping_at.strftime("%Y-%m-%d %H:%M:%S") if e.last_ping_at else None,
        "last_ping_status": e.last_ping_status or "unknown",
        "last_ping_message": e.last_ping_message or "",
        "last_ping_ms": e.last_ping_ms,
    }


@router.get("/api/equipment")
def list_equipment(db: Session = Depends(get_db)):
    items = db.query(Equipment).order_by(Equipment.name).all()
    return [_serialize(e) for e in items]


@router.post("/api/equipment/{equipment_id}/test-connection")
def test_equipment_connection(equipment_id: int):
    """단일 설비 FTP/SFTP 로그인까지 시도해 연결 상태를 갱신한다."""
    result = health_check.check_equipment(equipment_id, protocol_login=True)
    if result.get("status") not in ("ok", "failed"):
        raise HTTPException(status_code=404, detail=result.get("message", "설비를 찾을 수 없습니다."))
    return result


@router.post("/api/equipment/health-check")
def run_health_check():
    """활성 설비 전체에 대해 TCP ping 기반 헬스체크 실행."""
    results = health_check.check_all(only_active=True, protocol_login=False)
    summary = {
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
    }
    return {"results": results, "summary": summary}


@router.get("/api/equipment/health-status")
def health_status(db: Session = Depends(get_db)):
    items = db.query(Equipment).filter(Equipment.is_active == True).order_by(Equipment.name).all()
    statuses = [_serialize(e) for e in items]
    summary = {
        "total": len(statuses),
        "ok":      sum(1 for s in statuses if s["last_ping_status"] == "ok"),
        "failed":  sum(1 for s in statuses if s["last_ping_status"] == "failed"),
        "unknown": sum(1 for s in statuses if s["last_ping_status"] == "unknown"),
    }
    return {"equipment": statuses, "summary": summary}


@router.post("/api/equipment")
def create_equipment(data: EquipmentCreate, db: Session = Depends(get_db)):
    existing = db.query(Equipment).filter(Equipment.ip == data.ip).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"IP {data.ip} 는 이미 등록되어 있습니다.")
    eq = Equipment(**data.model_dump())
    db.add(eq)
    db.commit()
    db.refresh(eq)
    return {"id": eq.id, "message": f"설비 '{eq.name}' 이(가) 등록되었습니다."}


@router.put("/api/equipment/{equipment_id}")
def update_equipment(equipment_id: int, data: EquipmentUpdate, db: Session = Depends(get_db)):
    eq = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="설비를 찾을 수 없습니다.")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(eq, field, value)
    eq.updated_at = datetime.now()
    db.commit()
    return {"message": f"설비 '{eq.name}' 이(가) 수정되었습니다."}


@router.delete("/api/equipment/{equipment_id}")
def delete_equipment(equipment_id: int, db: Session = Depends(get_db)):
    eq = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="설비를 찾을 수 없습니다.")
    name = eq.name
    db.delete(eq)
    db.commit()
    return {"message": f"설비 '{name}' 이(가) 삭제되었습니다."}


@router.post("/api/equipment/{equipment_id}/toggle")
def toggle_equipment(equipment_id: int, db: Session = Depends(get_db)):
    eq = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not eq:
        raise HTTPException(status_code=404, detail="설비를 찾을 수 없습니다.")
    eq.is_active = not eq.is_active
    eq.updated_at = datetime.now()
    db.commit()
    status = "활성화" if eq.is_active else "비활성화"
    return {"message": f"설비 '{eq.name}' 이(가) {status}되었습니다.", "is_active": eq.is_active}
