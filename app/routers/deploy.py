from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import Equipment, DeployLog, GenerateLog

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class DeployRequest(BaseModel):
    equipment_ids: list[int] | None = None  # None = 전체 배포
    triggered_by: str = "manual"


@router.post("/api/deploy/run")
async def run_deploy(data: DeployRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from app.services.deployer import run_full_deploy, deploy_to_equipment
    from app.services.file_generator import generate_all_files

    if data.equipment_ids:
        equipment_list = db.query(Equipment).filter(
            Equipment.id.in_(data.equipment_ids),
            Equipment.is_active == True
        ).all()
    else:
        equipment_list = db.query(Equipment).filter(Equipment.is_active == True).all()

    if not equipment_list:
        raise HTTPException(status_code=400, detail="배포할 활성 설비가 없습니다.")

    background_tasks.add_task(run_full_deploy, equipment_list, data.triggered_by)
    return {"message": f"{len(equipment_list)}개 설비에 배포를 시작했습니다. 잠시 후 결과를 확인하세요."}


@router.post("/api/deploy/generate")
async def run_generate(background_tasks: BackgroundTasks, triggered_by: str = "manual"):
    from app.services.file_generator import generate_all_files
    background_tasks.add_task(generate_all_files, triggered_by)
    return {"message": "파일 생성을 시작했습니다."}


@router.get("/api/deploy/status/today")
def today_status(db: Session = Depends(get_db)):
    from datetime import date
    today = date.today()

    generate_logs = db.query(GenerateLog).filter(
        GenerateLog.generated_at >= today
    ).order_by(GenerateLog.generated_at.desc()).all()

    equipment_list = db.query(Equipment).filter(Equipment.is_active == True).all()
    equipment_ids = [e.id for e in equipment_list]

    deploy_logs = db.query(DeployLog).filter(
        DeployLog.deployed_at >= today,
        DeployLog.equipment_id.in_(equipment_ids)
    ).order_by(DeployLog.deployed_at.desc()).all()

    deploy_map: dict = {}
    for log in deploy_logs:
        eq_id = log.equipment_id
        if eq_id not in deploy_map:
            deploy_map[eq_id] = {}
        if log.file_type not in deploy_map[eq_id]:
            deploy_map[eq_id][log.file_type] = {
                "status": log.status,
                "message": log.message,
                "deployed_at": log.deployed_at.strftime("%H:%M:%S"),
            }

    equipment_status = []
    for eq in equipment_list:
        eq_logs = deploy_map.get(eq.id, {})
        equipment_status.append({
            "id": eq.id,
            "name": eq.name,
            "ip": eq.ip,
            "file_X": eq_logs.get("X", {"status": "pending"}),
            "file_Y": eq_logs.get("Y", {"status": "pending"}),
        })

    return {
        "generate_logs": [
            {
                "file_type": g.file_type,
                "filename": g.filename,
                "status": g.status,
                "message": g.message,
                "generated_at": g.generated_at.strftime("%H:%M:%S"),
            }
            for g in generate_logs
        ],
        "equipment_status": equipment_status,
        "summary": {
            "total": len(equipment_list),
            "success": sum(
                1 for e in equipment_status
                if e["file_X"].get("status") == "success" and e["file_Y"].get("status") == "success"
            ),
            "failed": sum(
                1 for e in equipment_status
                if e["file_X"].get("status") == "failed" or e["file_Y"].get("status") == "failed"
            ),
            "pending": sum(
                1 for e in equipment_status
                if e["file_X"].get("status") == "pending" or e["file_Y"].get("status") == "pending"
            ),
        },
    }
