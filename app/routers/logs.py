"""
routers/logs.py — 배포/생성 로그 조회 API

URL 목록:
  GET /logs                  → 로그 HTML 페이지
  GET /api/logs/deploy       → 배포 로그 목록 (필터: equipment_id, status)
  GET /api/logs/generate     → 파일 생성 로그 목록
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import DeployLog, GenerateLog

router    = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request):
    """로그 페이지 HTML을 반환한다. 실제 데이터는 JS가 API를 호출해 채운다."""
    return templates.TemplateResponse("logs.html", {"request": request, "active_page": "logs"})


@router.get("/api/logs/deploy")
def deploy_logs(
    limit:        int       = 100,
    equipment_id: int | None = None,   # 특정 설비만 필터 (None = 전체)
    status:       str | None = None,   # "success" / "failed" (None = 전체)
    db: Session = Depends(get_db),
):
    """
    배포 로그를 최신순으로 반환한다.

    joinedload(DeployLog.equipment) : N+1 쿼리 방지를 위해 설비 정보를 함께 로드.
    설비가 삭제된 경우 log.equipment 가 None이 되므로 "삭제된 설비" 문자열을 표시.
    """
    query = db.query(DeployLog).options(joinedload(DeployLog.equipment))

    if equipment_id:
        query = query.filter(DeployLog.equipment_id == equipment_id)
    if status:
        query = query.filter(DeployLog.status == status)

    logs = query.order_by(DeployLog.deployed_at.desc()).limit(limit).all()
    return [
        {
            "id":             log.id,
            "equipment_name": log.equipment.name if log.equipment else "삭제된 설비",
            "equipment_ip":   log.equipment.ip   if log.equipment else "-",
            "file_type":      log.file_type,
            "status":         log.status,
            "message":        log.message,
            "deployed_at":    log.deployed_at.strftime("%Y-%m-%d %H:%M:%S"),
            "triggered_by":   log.triggered_by,
        }
        for log in logs
    ]


@router.get("/api/logs/generate")
def generate_logs(limit: int = 100, db: Session = Depends(get_db)):
    """파일 생성 로그를 최신순으로 반환한다."""
    logs = db.query(GenerateLog).order_by(GenerateLog.generated_at.desc()).limit(limit).all()
    return [
        {
            "id":           log.id,
            "file_type":    log.file_type,
            "filename":     log.filename,
            "status":       log.status,
            "message":      log.message,
            "generated_at": log.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "triggered_by": log.triggered_by,
        }
        for log in logs
    ]
