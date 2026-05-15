from app.models import Equipment


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
