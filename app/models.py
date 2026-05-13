"""
models.py — SQLAlchemy ORM 테이블 정의

각 클래스 = DB 테이블 1개.
Mapped / mapped_column 은 SQLAlchemy 2.x 스타일로, 타입 힌트와 컬럼 정의를 한 줄에 표현한다.
"""
from datetime import datetime
from sqlalchemy import Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


# ── 설비 테이블 ──────────────────────────────────────────────────
class Equipment(Base):
    """
    FTP 배포 대상 설비 정보.

    is_active=False 로 설정하면 자동 배포 및 헬스체크에서 제외된다.
    """
    __tablename__ = "equipment"

    id:          Mapped[int]  = mapped_column(Integer, primary_key=True, index=True)
    name:        Mapped[str]  = mapped_column(String(100), nullable=False)   # 설비명 (화면 표시용)
    ip:          Mapped[str]  = mapped_column(String(50),  nullable=False)   # FTP 서버 IP
    port:        Mapped[int]  = mapped_column(Integer, default=21)           # FTP 포트 (FTP=21, SFTP=22)
    ftp_user:    Mapped[str]  = mapped_column(String(100), default="")       # FTP 로그인 ID
    ftp_pass:    Mapped[str]  = mapped_column(String(200), default="")       # FTP 로그인 PW (평문 저장)
    ftp_path:    Mapped[str]  = mapped_column(String(500), default="/")      # FTP 기본 경로 (레거시, 현재 미사용)
    use_sftp:    Mapped[bool] = mapped_column(Boolean, default=False)        # True면 SFTP, False면 FTP
    is_active:   Mapped[bool] = mapped_column(Boolean, default=True)         # 비활성화하면 배포·점검 제외
    description: Mapped[str]  = mapped_column(Text, default="")              # 메모
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    # ── 헬스체크 결과 컬럼 (ALTER TABLE 마이그레이션으로 추가됨) ──
    last_ping_at:      Mapped[datetime | None] = mapped_column(DateTime, nullable=True)   # 마지막 점검 시각
    last_ping_status:  Mapped[str]  = mapped_column(String(20), default="unknown")        # ok / failed / unknown
    last_ping_message: Mapped[str]  = mapped_column(Text, default="")                    # 점검 결과 메시지
    last_ping_ms:      Mapped[int | None] = mapped_column(Integer, nullable=True)         # 응답 속도(ms)

    # 이 설비와 연결된 배포 로그 목록 (1:N 관계)
    deploy_logs: Mapped[list["DeployLog"]] = relationship("DeployLog", back_populates="equipment")


# ── 파일 템플릿 테이블 ────────────────────────────────────────────
class FileTemplate(Base):
    """
    XML 파일 생성에 사용하는 포맷 텍스트를 DB에 저장.
    현재 실제 생성 로직에서는 파일(static_xml_template.txt)을 사용하며,
    이 테이블은 향후 UI에서 포맷 수정 기능 구현 시 활용 예정이다.
    """
    __tablename__ = "file_template"

    id:          Mapped[int]  = mapped_column(Integer, primary_key=True, index=True)
    file_type:   Mapped[str]  = mapped_column(String(10), nullable=False)   # "YieldConvDef" 또는 "RejectMapFile"
    filename:    Mapped[str]  = mapped_column(String(200), nullable=False)  # 생성될 파일명
    content:     Mapped[str]  = mapped_column(Text, default="")             # 템플릿 내용
    description: Mapped[str]  = mapped_column(Text, default="")
    is_active:   Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by:  Mapped[str]  = mapped_column(String(100), default="")      # 마지막 수정자


# ── 배포 로그 테이블 ──────────────────────────────────────────────
class DeployLog(Base):
    """
    설비 1대에 파일 1개를 전송할 때마다 1행이 기록된다.
    equipment_id=NULL 인 경우는 설비가 삭제됐지만 로그는 보존된 상태.
    """
    __tablename__ = "deploy_log"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    equipment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("equipment.id"), nullable=True)
    file_type:    Mapped[str] = mapped_column(String(10),  nullable=False)  # "YieldConvDef" 또는 "RejectMapFile"
    status:       Mapped[str] = mapped_column(String(20),  nullable=False)  # "success" / "failed" / "skipped"
    message:      Mapped[str] = mapped_column(Text, default="")             # 성공 경로 또는 오류 메시지
    deployed_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    triggered_by: Mapped[str] = mapped_column(String(50),  default="scheduler")  # "scheduler" 또는 "manual"

    # 외래키로 연결된 설비 객체 (삭제된 설비면 None)
    equipment: Mapped["Equipment | None"] = relationship("Equipment", back_populates="deploy_logs")


# ── 파일 생성 로그 테이블 ─────────────────────────────────────────
class GenerateLog(Base):
    """
    XML 파일 생성 작업마다 1행이 기록된다.
    설비와 무관하게 서버 측 생성 결과만 추적한다.
    """
    __tablename__ = "generate_log"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_type:    Mapped[str] = mapped_column(String(10),  nullable=False)   # "YieldConvDef" 또는 "RejectMapFile"
    filename:     Mapped[str] = mapped_column(String(200), nullable=False)   # 생성된 파일명
    status:       Mapped[str] = mapped_column(String(20),  nullable=False)   # "success" / "failed"
    message:      Mapped[str] = mapped_column(Text, default="")              # 결과 설명
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    triggered_by: Mapped[str] = mapped_column(String(50), default="scheduler")


# ── 시스템 설정 테이블 ────────────────────────────────────────────
class SystemConfig(Base):
    """
    key-value 형태의 시스템 설정 저장소.
    현재 직접 사용되지 않으며, 향후 UI에서 설정 변경 기능에 활용 예정.
    """
    __tablename__ = "system_config"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key:         Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value:       Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    updated_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
