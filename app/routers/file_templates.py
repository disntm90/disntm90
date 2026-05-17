"""
routers/file_templates.py — XML 포맷 템플릿 관리 API

URL 목록:
  GET    /templates                  → 포맷 관리 HTML 페이지
  GET    /api/templates              → 템플릿 목록
  GET    /api/templates/{id}         → 특정 템플릿 조회
  POST   /api/templates              → 템플릿 추가
  PUT    /api/templates/{id}         → 템플릿 수정
  DELETE /api/templates/{id}         → 템플릿 삭제

현재 실제 파일 생성(file_generator.py)은 data/static_xml_template.txt를 직접 읽는다.
이 테이블은 향후 UI에서 템플릿을 수정하면 실제 파일 생성에 반영하는 기능을 붙일 때 사용한다.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import FileTemplate

router    = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class TemplateCreate(BaseModel):
    """템플릿 추가 요청 바디"""
    file_type:   str   # "YieldConvDef" 또는 "RejectMapFile"
    filename:    str
    content:     str
    description: str = ""
    updated_by:  str = ""


class TemplateUpdate(BaseModel):
    """템플릿 수정 요청 바디 (변경할 필드만 전달)"""
    filename:    str | None = None
    content:     str | None = None
    description: str | None = None
    updated_by:  str = ""


@router.get("/templates", response_class=HTMLResponse)
def templates_page(request: Request, db: Session = Depends(get_db)):
    """포맷 관리 HTML 페이지를 렌더링한다."""
    items = db.query(FileTemplate).order_by(FileTemplate.file_type, FileTemplate.filename).all()
    return templates.TemplateResponse(
        "file_templates.html",
        {"request": request, "template_list": items, "active_page": "templates"}
    )


@router.get("/api/templates")
def list_templates(db: Session = Depends(get_db)):
    """템플릿 전체 목록을 반환한다."""
    items = db.query(FileTemplate).order_by(FileTemplate.file_type).all()
    return [
        {
            "id":          t.id,
            "file_type":   t.file_type,
            "filename":    t.filename,
            "content":     t.content,
            "description": t.description,
            "is_active":   t.is_active,
            "updated_at":  t.updated_at.strftime("%Y-%m-%d %H:%M"),
            "updated_by":  t.updated_by,
        }
        for t in items
    ]


@router.get("/api/templates/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    """특정 템플릿을 조회한다."""
    t = db.query(FileTemplate).filter(FileTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")
    return {
        "id":          t.id,
        "file_type":   t.file_type,
        "filename":    t.filename,
        "content":     t.content,
        "description": t.description,
        "is_active":   t.is_active,
        "updated_at":  t.updated_at.strftime("%Y-%m-%d %H:%M"),
        "updated_by":  t.updated_by,
    }


@router.post("/api/templates")
def create_template(data: TemplateCreate, db: Session = Depends(get_db)):
    """템플릿을 새로 추가한다."""
    t = FileTemplate(**data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id, "message": f"템플릿 '{t.filename}' 이(가) 생성되었습니다."}


@router.put("/api/templates/{template_id}")
def update_template(template_id: int, data: TemplateUpdate, db: Session = Depends(get_db)):
    """템플릿을 수정한다. 전달된 필드만 변경한다."""
    t = db.query(FileTemplate).filter(FileTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(t, field, value)
    t.updated_at = datetime.now()
    db.commit()
    return {"message": f"템플릿 '{t.filename}' 이(가) 수정되었습니다."}


@router.delete("/api/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    """템플릿을 삭제한다."""
    t = db.query(FileTemplate).filter(FileTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")
    name = t.filename
    db.delete(t)
    db.commit()
    return {"message": f"템플릿 '{name}' 이(가) 삭제되었습니다."}
