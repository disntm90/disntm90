"""
routers/deploy.py — 파일 생성 및 FTP 배포 API

URL 목록:
  POST /api/deploy/run              → 전체(또는 선택) 설비 배포 (백그라운드)
  POST /api/deploy/generate         → 파일 생성만 실행 (백그라운드)
  GET  /api/deploy/status/today     → 오늘의 생성/배포 현황 조회
"""

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import Equipment, DeployLog, GenerateLog

router    = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class DeployRequest(BaseModel):
    """배포 요청 바디 스키마"""
    equipment_ids: list[int] | None = None  # None이면 모든 활성 설비에 배포
    triggered_by:  str = "manual"


@router.post("/api/deploy/run")
async def run_deploy(data: DeployRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    지정된(또는 전체) 설비에 배포를 실행한다.

    BackgroundTasks를 사용해 응답을 즉시 반환하고,
    실제 파일 생성 + FTP 전송은 백그라운드에서 수행한다.
    클라이언트는 결과를 /api/deploy/status/today 로 폴링해 확인한다.
    """
    from app.services.deployer import run_full_deploy

    if data.equipment_ids:
        # 특정 설비 ID 목록이 주어진 경우
        equipment_list = db.query(Equipment).filter(
            Equipment.id.in_(data.equipment_ids),
            Equipment.is_active == True
        ).all()
    else:
        # 전체 활성 설비
        equipment_list = db.query(Equipment).filter(Equipment.is_active == True).all()

    if not equipment_list:
        raise HTTPException(status_code=400, detail="배포할 활성 설비가 없습니다.")

    # 배포 작업을 백그라운드에 예약하고 바로 응답 반환
    background_tasks.add_task(run_full_deploy, equipment_list, data.triggered_by)
    return {"message": f"{len(equipment_list)}개 설비에 배포를 시작했습니다. 잠시 후 결과를 확인하세요."}


@router.post("/api/deploy/generate")
async def run_generate(background_tasks: BackgroundTasks, triggered_by: str = "manual"):
    """
    파일 생성만 백그라운드로 실행한다.
    설비가 없는 상태에서 파일만 미리 만들어두고 싶을 때 사용한다.
    """
    from app.services.file_generator import generate_all_files
    background_tasks.add_task(generate_all_files, triggered_by)
    return {"message": "파일 생성을 시작했습니다."}


@router.get("/api/deploy/status/today")
def today_status(db: Session = Depends(get_db)):
    """
    오늘(자정 이후)의 파일 생성 이력과 설비별 배포 상태를 반환한다.

    반환 구조:
      generate_logs  : 오늘 생성된 파일 목록 (최신순)
      equipment_status: 활성 설비별 YieldConvDef/RejectMapFile 배포 결과
      summary        : 성공/실패/미배포 설비 수 집계
    """
    from datetime import date
    today = date.today()  # 오늘 자정 (00:00:00) 기준

    # 오늘 생성된 파일 로그 조회 (최신순)
    generate_logs = db.query(GenerateLog).filter(
        GenerateLog.generated_at >= today
    ).order_by(GenerateLog.generated_at.desc()).all()

    # 활성 설비 목록 조회
    equipment_list = db.query(Equipment).filter(Equipment.is_active == True).all()
    equipment_ids  = [e.id for e in equipment_list]

    # 오늘 배포 로그 조회 (활성 설비 대상, 최신순)
    deploy_logs = db.query(DeployLog).filter(
        DeployLog.deployed_at >= today,
        DeployLog.equipment_id.in_(equipment_ids)
    ).order_by(DeployLog.deployed_at.desc()).all()

    # 설비별 · 파일타입별로 가장 최근 배포 결과만 남기기
    # 구조: {equipment_id: {file_type: {status, message, deployed_at}}}
    deploy_map: dict = {}
    for log in deploy_logs:
        eq_id = log.equipment_id
        if eq_id not in deploy_map:
            deploy_map[eq_id] = {}
        # 이미 해당 파일타입이 있으면 건너뜀 (내림차순 정렬로 첫 번째 = 최신)
        if log.file_type not in deploy_map[eq_id]:
            deploy_map[eq_id][log.file_type] = {
                "status":      log.status,
                "message":     log.message,
                "deployed_at": log.deployed_at.strftime("%H:%M:%S"),
            }

    # 설비별 배포 상태 구성
    equipment_status = []
    for eq in equipment_list:
        eq_logs = deploy_map.get(eq.id, {})
        equipment_status.append({
            "id":                 eq.id,
            "name":               eq.name,
            "ip":                 eq.ip,
            "group_name":         eq.group_name or "기타",
            "last_ping_status":   eq.last_ping_status or "unknown",
            # 배포 이력 없으면 pending 상태로 표시
            "file_YieldConvDef":  eq_logs.get("YieldConvDef",  {"status": "pending"}),
            "file_RejectMapFile": eq_logs.get("RejectMapFile", {"status": "pending"}),
        })

    return {
        "generate_logs": [
            {
                "file_type":    g.file_type,
                "filename":     g.filename,
                "status":       g.status,
                "message":      g.message,
                "generated_at": g.generated_at.strftime("%H:%M:%S"),
            }
            for g in generate_logs
        ],
        "equipment_status": equipment_status,
        "summary": {
            "total":   len(equipment_list),
            # 두 파일 모두 success인 설비만 성공으로 집계
            "success": sum(
                1 for e in equipment_status
                if e["file_YieldConvDef"].get("status") == "success"
                and e["file_RejectMapFile"].get("status") == "success"
            ),
            # 두 파일 중 하나라도 failed면 실패로 집계
            "failed": sum(
                1 for e in equipment_status
                if e["file_YieldConvDef"].get("status") == "failed"
                or e["file_RejectMapFile"].get("status") == "failed"
            ),
            # 아직 배포 이력이 없는 설비 수
            "pending": sum(
                1 for e in equipment_status
                if e["file_YieldConvDef"].get("status") == "pending"
                or e["file_RejectMapFile"].get("status") == "pending"
            ),
        },
    }
