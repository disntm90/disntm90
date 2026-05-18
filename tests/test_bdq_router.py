"""tests/test_bdq_router.py — BDQ 쿼리 데이터 라우터 테스트"""
import pandas as pd
import pytest
from fastapi import HTTPException


def _fake_df(rows):
    """간이 DataFrame 생성: rows=[("BGA001", "12"), ...]"""
    return pd.DataFrame(rows, columns=["code_type", "code_id"])


def test_query_returns_table_and_rows(monkeypatch):
    from app.routers import bdq
    monkeypatch.setattr(bdq, "_fetch_scrap_data", lambda: _fake_df([
        ("BGA001", "12"),
        ("3D_M01", "5"),
        ("BBI_X",  "9"),
        ("TOPSMI_A", "1"),
        ("ETC_Z",  "7"),
    ]))
    result = bdq.query_bdq_data()
    assert result["table"] == "mos_tsp_smi.gpm_tp_be_mng_sbl_scrap_code"
    assert "queried_at" in result
    assert len(result["rows"]) == 5
    assert result["rows"][0] == {"code_type": "BGA001", "code_id": "12"}


def test_query_summary_groups_by_prefix(monkeypatch):
    from app.routers import bdq
    monkeypatch.setattr(bdq, "_fetch_scrap_data", lambda: _fake_df([
        ("BGA001", "1"), ("BGA002", "2"),
        ("3D_M01", "3"),
        ("BBI_X",  "4"),
        ("TOPSMI_A", "5"),
        ("ETC_Z",  "6"), ("OTHER", "7"),
    ]))
    result = bdq.query_bdq_data()
    assert result["summary"]["total"] == 7
    assert result["summary"]["groups"] == {
        "BGA":    2,
        "3D":     1,
        "BBI":    1,
        "TOPSMI": 1,
        "기타":   2,
    }


def test_query_raises_503_when_fetch_returns_none(monkeypatch):
    from app.routers import bdq
    monkeypatch.setattr(bdq, "_fetch_scrap_data", lambda: None)
    with pytest.raises(HTTPException) as exc:
        bdq.query_bdq_data()
    assert exc.value.status_code == 503
    assert "BDQ" in exc.value.detail


def test_bdq_page_renders():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    res = client.get("/bdq")
    assert res.status_code == 200
    assert "쿼리 데이터" in res.text


def test_nav_has_bdq_link():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert 'href="/bdq"' in res.text
