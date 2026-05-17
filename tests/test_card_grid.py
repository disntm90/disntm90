"""tests/test_card_grid.py — 설비 카드 그리드 관련 테스트"""
from app.models import Equipment


def test_equipment_has_group_name_field(db):
    eq = Equipment(name="테스트-A1", ip="192.168.1.1", group_name="A라인")
    db.add(eq)
    db.commit()
    db.refresh(eq)
    assert eq.group_name == "A라인"


def test_equipment_group_name_is_optional(db):
    eq = Equipment(name="테스트-B1", ip="192.168.1.2")
    db.add(eq)
    db.commit()
    db.refresh(eq)
    assert eq.group_name is None


def test_serialize_includes_group_name(db):
    from app.routers.equipment import _serialize
    eq = Equipment(name="테스트-C1", ip="192.168.1.3", group_name="C라인")
    db.add(eq)
    db.commit()
    db.refresh(eq)
    result = _serialize(eq)
    assert result["group_name"] == "C라인"


def test_serialize_group_name_none_when_not_set(db):
    from app.routers.equipment import _serialize
    eq = Equipment(name="테스트-D1", ip="192.168.1.4")
    db.add(eq)
    db.commit()
    db.refresh(eq)
    result = _serialize(eq)
    assert result["group_name"] is None
