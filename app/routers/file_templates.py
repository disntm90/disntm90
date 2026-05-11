from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import FileTemplate

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class TemplateCreate(BaseModel):
    file_type: str  # "X" or "Y"
    filename: str
    content: str
    description: str = ""
    updated_by: str = ""


class TemplateUpdate(BaseModel):
    filename: str | None = None
    content: str | None = None
    description: str | None = None
    updated_by: str = ""


@router.get("/templates", response_class=HTMLResponse)
def templates_page(request: Request, db: Session = Depends(get_db)):
    items = db.query(FileTemplate).order_by(FileTemplate.file_type, FileTemplate.filename).all()
    return templates.TemplateResponse("file_templates.html", {"request": request, "template_list": items})


@router.get("/api/templates")
def list_templates(db: Session = Depends(get_db)):
    items = db.query(FileTemplate).order_by(FileTemplate.file_type).all()
    return [
        {
            "id": t.id,
            "file_type": t.file_type,
            "filename": t.filename,
            "content": t.content,
            "description": t.description,
            "is_active": t.is_active,
            "updated_at": t.updated_at.strftime("%Y-%m-%d %H:%M"),
            "updated_by": t.updated_by,
        }
        for t in items
    ]


@router.get("/api/templates/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(FileTemplate).filter(FileTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")
    return {
        "id": t.id,
        "file_type": t.file_type,
        "filename": t.filename,
        "content": t.content,
        "description": t.description,
        "is_active": t.is_active,
        "updated_at": t.updated_at.strftime("%Y-%m-%d %H:%M"),
        "updated_by": t.updated_by,
    }


@router.post("/api/templates")
def create_template(data: TemplateCreate, db: Session = Depends(get_db)):
    if data.file_type not in ("X", "Y"):
        raise HTTPException(status_code=400, detail="파일 타입은 X 또는 Y 이어야 합니다.")
    t = FileTemplate(**data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id, "message": f"템플릿 '{t.filename}' 이(가) 생성되었습니다."}


@router.put("/api/templates/{template_id}")
def update_template(template_id: int, data: TemplateUpdate, db: Session = Depends(get_db)):
    t = db.query(FileTemplate).filter(FileTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")
    update_data = data.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(t, field, value)
    t.updated_at = datetime.now()
    db.commit()
    return {"message": f"템플릿 '{t.filename}' 이(가) 수정되었습니다."}


@router.delete("/api/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(FileTemplate).filter(FileTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")
    name = t.filename
    db.delete(t)
    db.commit()
    return {"message": f"템플릿 '{name}' 이(가) 삭제되었습니다."}
