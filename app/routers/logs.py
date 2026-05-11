from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import DeployLog, GenerateLog

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request):
    return templates.TemplateResponse("logs.html", {"request": request})


@router.get("/api/logs/deploy")
def deploy_logs(
    limit: int = 100,
    equipment_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DeployLog).options(joinedload(DeployLog.equipment))

    if equipment_id:
        query = query.filter(DeployLog.equipment_id == equipment_id)
    if status:
        query = query.filter(DeployLog.status == status)

    logs = query.order_by(DeployLog.deployed_at.desc()).limit(limit).all()
    return [
        {
            "id": log.id,
            "equipment_name": log.equipment.name if log.equipment else "삭제된 설비",
            "equipment_ip": log.equipment.ip if log.equipment else "-",
            "file_type": log.file_type,
            "status": log.status,
            "message": log.message,
            "deployed_at": log.deployed_at.strftime("%Y-%m-%d %H:%M:%S"),
            "triggered_by": log.triggered_by,
        }
        for log in logs
    ]


@router.get("/api/logs/generate")
def generate_logs(limit: int = 100, db: Session = Depends(get_db)):
    logs = db.query(GenerateLog).order_by(GenerateLog.generated_at.desc()).limit(limit).all()
    return [
        {
            "id": log.id,
            "file_type": log.file_type,
            "filename": log.filename,
            "status": log.status,
            "message": log.message,
            "generated_at": log.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "triggered_by": log.triggered_by,
        }
        for log in logs
    ]
