from datetime import datetime
from sqlalchemy import Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    ip: Mapped[str] = mapped_column(String(50), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=21)
    ftp_user: Mapped[str] = mapped_column(String(100), default="")
    ftp_pass: Mapped[str] = mapped_column(String(200), default="")
    ftp_path: Mapped[str] = mapped_column(String(500), default="/")
    use_sftp: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    deploy_logs: Mapped[list["DeployLog"]] = relationship("DeployLog", back_populates="equipment")


class FileTemplate(Base):
    __tablename__ = "file_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "X" or "Y"
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by: Mapped[str] = mapped_column(String(100), default="")


class DeployLog(Base):
    __tablename__ = "deploy_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    equipment_id: Mapped[int] = mapped_column(Integer, ForeignKey("equipment.id"), nullable=True)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "X", "Y", "ALL"
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "success", "failed", "skipped"
    message: Mapped[str] = mapped_column(Text, default="")
    deployed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    triggered_by: Mapped[str] = mapped_column(String(50), default="scheduler")  # "scheduler" or "manual"

    equipment: Mapped["Equipment"] = relationship("Equipment", back_populates="deploy_logs")


class GenerateLog(Base):
    __tablename__ = "generate_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    triggered_by: Mapped[str] = mapped_column(String(50), default="scheduler")


class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
