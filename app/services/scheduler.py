"""APScheduler를 사용한 자동 배포 + 주기적 설비 헬스체크 스케줄러."""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from config import SCHEDULE_HOUR, SCHEDULE_MINUTE, HEALTH_CHECK_INTERVAL_MIN

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _scheduled_deploy_job():
    from app.database import SessionLocal
    from app.models import Equipment
    from app.services.deployer import run_full_deploy

    logger.info("스케줄 배포 작업 시작")
    db = SessionLocal()
    try:
        equipment_list = db.query(Equipment).filter(Equipment.is_active == True).all()
        if not equipment_list:
            logger.warning("활성 설비가 없습니다. 배포를 건너뜁니다.")
            return
        run_full_deploy(equipment_list, triggered_by="scheduler")
    finally:
        db.close()


def _scheduled_health_check_job():
    from app.services import health_check
    try:
        health_check.check_all(only_active=True, protocol_login=False)
    except Exception:
        logger.exception("주기적 헬스체크 실패")


def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Seoul")

    _scheduler.add_job(
        _scheduled_deploy_job,
        trigger=CronTrigger(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE),
        id="daily_deploy",
        name=f"매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} 자동 배포",
        replace_existing=True,
    )
    _scheduler.add_job(
        _scheduled_health_check_job,
        trigger=IntervalTrigger(minutes=HEALTH_CHECK_INTERVAL_MIN),
        id="health_check",
        name=f"{HEALTH_CHECK_INTERVAL_MIN}분 주기 설비 헬스체크",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        f"스케줄러 시작: 매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} 배포 / "
        f"{HEALTH_CHECK_INTERVAL_MIN}분마다 헬스체크"
    )


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("스케줄러 종료")


def get_scheduler_status() -> dict:
    if not _scheduler:
        return {"running": False, "next_run": None}

    deploy_job = _scheduler.get_job("daily_deploy")
    health_job = _scheduler.get_job("health_check")
    return {
        "running": _scheduler.running,
        "next_run":         deploy_job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if deploy_job and deploy_job.next_run_time else None,
        "next_health_run":  health_job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if health_job and health_job.next_run_time else None,
        "schedule":         f"매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}",
        "health_interval":  f"{HEALTH_CHECK_INTERVAL_MIN}분",
    }
