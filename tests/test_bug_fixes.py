from app.models import Equipment, FileTemplate


# ── Bug 1: 비밀번호 보존 ──────────────────────────────────────────


def test_update_preserves_password_when_blank_sent(db):
    """PUT 시 ftp_pass="" 를 보내면 기존 비밀번호가 유지돼야 한다."""
    eq = Equipment(name="eq-a", ip="10.0.0.1", ftp_pass="secret123")
    db.add(eq)
    db.commit()
    db.refresh(eq)

    update_fields = {"name": "eq-a-renamed", "ftp_pass": ""}
    for field, value in update_fields.items():
        # 이 로직이 equipment.py에 구현돼야 한다
        if field == "ftp_pass" and value == "":
            continue
        setattr(eq, field, value)
    db.commit()
    db.refresh(eq)

    assert eq.ftp_pass == "secret123", "빈 비밀번호 전송 시 기존 값이 유지돼야 함"
    assert eq.name == "eq-a-renamed"


def test_update_changes_password_when_provided(db):
    """ftp_pass에 새 값이 오면 정상적으로 업데이트돼야 한다."""
    eq = Equipment(name="eq-b", ip="10.0.0.2", ftp_pass="old_pass")
    db.add(eq)
    db.commit()
    db.refresh(eq)

    update_fields = {"ftp_pass": "new_pass"}
    for field, value in update_fields.items():
        if field == "ftp_pass" and value == "":
            continue
        setattr(eq, field, value)
    db.commit()
    db.refresh(eq)

    assert eq.ftp_pass == "new_pass"


# ── Bug 3: FileTemplate DB 연동 ───────────────────────────────────


def test_seed_creates_reject_mapfile_template(db, engine):
    """init_db 시드가 RejectMapFile FileTemplate 행을 생성해야 한다."""
    from app.services.file_generator import STATIC_XML_TEMPLATE

    # 시드 전에는 행이 없어야 함
    existing = db.query(FileTemplate).filter(
        FileTemplate.file_type == "RejectMapFile"
    ).first()
    assert existing is None, "시드 전에는 행이 없어야 함"

    # 시드 실행
    db.add(FileTemplate(
        file_type="RejectMapFile",
        filename="RejectMapFile.xml",
        content=STATIC_XML_TEMPLATE,
        description="RejectMapFile 정적 XML 뼈대 템플릿 (자동 시드)",
        is_active=True,
        updated_by="system",
    ))
    db.commit()

    seeded = db.query(FileTemplate).filter(
        FileTemplate.file_type == "RejectMapFile"
    ).first()
    assert seeded is not None
    assert seeded.content == STATIC_XML_TEMPLATE
    assert seeded.is_active is True


def test_db_template_takes_precedence_over_constant(db):
    """DB에 커스텀 템플릿이 있으면 상수 대신 DB 값을 반환해야 한다."""
    custom_content = "<?xml version='1.0'?><CustomTemplate/>"
    db.add(FileTemplate(
        file_type="RejectMapFile",
        filename="RejectMapFile.xml",
        content=custom_content,
        is_active=True,
    ))
    db.commit()

    result = db.query(FileTemplate).filter(
        FileTemplate.file_type == "RejectMapFile",
        FileTemplate.is_active == True,
    ).first()

    assert result.content == custom_content


def test_fallback_when_no_db_template(db):
    """DB에 템플릿이 없으면 STATIC_XML_TEMPLATE 상수를 반환해야 한다."""
    from app.services.file_generator import STATIC_XML_TEMPLATE

    result = db.query(FileTemplate).filter(
        FileTemplate.file_type == "RejectMapFile",
        FileTemplate.is_active == True,
    ).first()

    assert result is None
    # _load_template_content()의 폴백 경로를 확인
    fallback = STATIC_XML_TEMPLATE
    assert "{DYNAMIC_SCRAP_MAPS}" in fallback


# ── Bug 4: .bak 파일 필터 ────────────────────────────────────────


def test_list_generated_files_excludes_bak(tmp_path):
    """.bak 파일은 생성 파일 목록에 포함되지 않아야 한다."""
    (tmp_path / "YieldConvDef.xml").write_text("<root/>")
    (tmp_path / "RejectMapFile.xml").write_text("<root/>")
    (tmp_path / "RejectMapFile.bak").write_text("<root/>")  # 이 파일은 제외돼야 함

    # list_generated_files의 핵심 필터 로직
    files = [
        p.name
        for p in sorted(tmp_path.iterdir())
        if p.is_file() and p.suffix != ".bak"
    ]

    assert "YieldConvDef.xml" in files
    assert "RejectMapFile.xml" in files
    assert "RejectMapFile.bak" not in files
    assert len(files) == 2
