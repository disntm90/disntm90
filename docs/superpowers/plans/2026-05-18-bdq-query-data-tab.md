# BDQ Query Data Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 네비게이션바에 신규 "쿼리 데이터" 페이지를 추가해 BDQ 테이블 원본 데이터를 UI에서 확인할 수 있게 한다.

**Architecture:** 신규 라우터(`app/routers/bdq.py`)와 신규 템플릿(`app/templates/bdq.html`)을 추가하고, `app/services/file_generator.py`의 `_fetch_scrap_data()`를 재사용한다. 페이지는 빈 셸로 렌더되고 JS가 `/api/bdq/query`를 호출해 데이터를 받아 클라이언트에서 렌더링한다(`dashboard.html`과 동일 패턴).

**Tech Stack:** FastAPI, Jinja2, Bootstrap 5, 순수 fetch + JS DOM 렌더링, pytest.

---

## File Structure

- **Create:** `app/routers/bdq.py` — `/bdq` 페이지 + `/api/bdq/query` JSON 엔드포인트
- **Create:** `app/templates/bdq.html` — 페이지 템플릿 (요약 카드 + 테이블 + 로딩/에러 상태)
- **Create:** `tests/test_bdq_router.py` — 라우터 단위 테스트 (`_fetch_scrap_data` 모킹)
- **Modify:** `app/main.py` — 라우터 등록
- **Modify:** `app/templates/base.html` — 네비게이션 메뉴 5번째 항목 추가

---

### Task 1: BDQ API 엔드포인트 + 라우터 모듈 + 테스트

**Files:**
- Create: `app/routers/bdq.py`
- Create: `tests/test_bdq_router.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_bdq_router.py` 신규 파일:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_bdq_router.py -v`
Expected: FAIL — `app.routers.bdq` 모듈이 없어 ImportError 발생

- [ ] **Step 3: 라우터 모듈 구현**

`app/routers/bdq.py` 신규 파일:

```python
"""
routers/bdq.py — BDQ 쿼리 데이터 확인 페이지

URL 목록:
  GET /bdq             → 쿼리 데이터 HTML 페이지
  GET /api/bdq/query   → BDQ 테이블 원본 데이터 + 요약 통계 (JSON)
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.file_generator import _fetch_scrap_data, _BDQ_TABLE

router    = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _classify_group(code_type: str) -> str:
    """code_type prefix로 그룹 분류 — generate_yield_condef()의 정렬 우선순위와 동일."""
    if code_type.startswith("BGA"):
        return "BGA"
    if code_type.startswith("3D"):
        return "3D"
    if code_type.startswith("BBI"):
        return "BBI"
    if code_type.startswith("TOPSMI"):
        return "TOPSMI"
    return "기타"


@router.get("/api/bdq/query")
def query_bdq_data():
    """
    BDQ 테이블 원본 데이터를 조회해 행 목록 + 그룹별 요약을 반환한다.
    매 호출마다 _fetch_scrap_data()가 BDQ 세션을 갱신하므로 최신 데이터를 받는다.
    """
    df = _fetch_scrap_data()
    if df is None:
        raise HTTPException(status_code=503, detail="BDQ 조회 실패: 로그인 실패 또는 데이터 없음")

    rows = [
        {"code_type": str(r.code_type), "code_id": str(r.code_id)}
        for r in df.itertuples(index=False)
    ]

    groups = {"BGA": 0, "3D": 0, "BBI": 0, "TOPSMI": 0, "기타": 0}
    for row in rows:
        groups[_classify_group(row["code_type"])] += 1

    return {
        "table":      _BDQ_TABLE,
        "queried_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rows":       rows,
        "summary":    {"total": len(rows), "groups": groups},
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_bdq_router.py -v`
Expected: PASS — 3개 테스트 모두 통과

- [ ] **Step 5: 커밋**

```bash
git add app/routers/bdq.py tests/test_bdq_router.py
git commit -m "feat: BDQ 쿼리 데이터 API 엔드포인트 추가"
```

---

### Task 2: 페이지 라우트 + 라우터 등록 + 네비게이션 메뉴

**Files:**
- Modify: `app/routers/bdq.py` (페이지 라우트 추가)
- Modify: `app/main.py` (라우터 등록)
- Modify: `app/templates/base.html` (네비게이션 메뉴 추가)
- Modify: `tests/test_bdq_router.py` (페이지 라우트 테스트 추가)

- [ ] **Step 1: 페이지 라우트 테스트 작성 (실패 테스트)**

`tests/test_bdq_router.py` 끝에 추가:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_bdq_router.py::test_bdq_page_renders tests/test_bdq_router.py::test_nav_has_bdq_link -v`
Expected: FAIL — 404 또는 nav에 링크 없음

- [ ] **Step 3: 페이지 라우트 추가**

`app/routers/bdq.py` 끝(파일 마지막)에 추가:

```python
@router.get("/bdq", response_class=HTMLResponse)
def bdq_page(request: Request):
    """쿼리 데이터 HTML 페이지를 렌더링한다."""
    return templates.TemplateResponse(
        "bdq.html",
        {"request": request, "active_page": "bdq"},
    )
```

- [ ] **Step 4: 신규 템플릿 placeholder 생성 (테스트 통과용 최소 셸)**

`app/templates/bdq.html` 신규 파일:

```html
{% extends "base.html" %}
{% block content %}
<div class="card">
  <div class="card-header">
    <h5 class="mb-0">📊 BDQ 쿼리 데이터</h5>
  </div>
  <div class="card-body">
    <div id="bdqPlaceholder">로딩 중...</div>
  </div>
</div>
{% endblock %}
```

(Task 3에서 본 구현으로 교체. 이 시점에는 페이지가 200을 반환하고 "쿼리 데이터" 텍스트를 포함하기만 하면 됨.)

- [ ] **Step 5: 라우터 등록**

`app/main.py`에서 import 라인 찾기:

```python
from app.routers import equipment, file_templates, deploy, logs, files
```

다음으로 변경:

```python
from app.routers import equipment, file_templates, deploy, logs, files, bdq
```

그리고 `app.include_router(files.router)` 다음 줄에 추가:

```python
app.include_router(bdq.router)             # /bdq, /api/bdq/*
```

- [ ] **Step 6: 네비게이션 메뉴 추가**

`app/templates/base.html`에서 `배포 로그` `<li>` 다음에 새 `<li>` 추가:

기존:

```html
        <li class="nav-item">
          <a class="nav-link {% if active_page == 'logs' %}active{% endif %}" href="/logs">배포 로그</a>
        </li>
      </ul>
```

다음으로 변경:

```html
        <li class="nav-item">
          <a class="nav-link {% if active_page == 'logs' %}active{% endif %}" href="/logs">배포 로그</a>
        </li>
        <li class="nav-item">
          <a class="nav-link {% if active_page == 'bdq' %}active{% endif %}" href="/bdq">쿼리 데이터</a>
        </li>
      </ul>
```

- [ ] **Step 7: 모든 테스트 통과 확인**

Run: `pytest tests/test_bdq_router.py -v`
Expected: PASS — 5개 테스트 모두 통과 (Task 1의 3개 + Task 2의 2개)

- [ ] **Step 8: 커밋**

```bash
git add app/routers/bdq.py app/main.py app/templates/base.html app/templates/bdq.html tests/test_bdq_router.py
git commit -m "feat: BDQ 쿼리 데이터 페이지 라우트 + 네비게이션 메뉴 추가"
```

---

### Task 3: BDQ 페이지 템플릿 본 구현 (UI)

**Files:**
- Modify: `app/templates/bdq.html` (Task 2의 placeholder를 본 UI로 교체)

- [ ] **Step 1: 템플릿 전체 교체**

`app/templates/bdq.html` 전체 내용을 다음으로 교체:

```html
{% extends "base.html" %}

{% block content %}
<div class="card">
  <div class="card-header d-flex justify-content-between align-items-center">
    <div>
      <h5 class="mb-1">📊 BDQ 쿼리 데이터</h5>
      <small class="text-muted">
        Table: <code id="bdqTable">—</code>
        · 조회 시각: <span id="bdqQueriedAt">—</span>
      </small>
    </div>
    <button id="bdqRefreshBtn" class="btn btn-outline-primary btn-sm">🔄 새로고침</button>
  </div>

  <div class="card-body">
    <div id="bdqError" class="alert alert-danger d-none"></div>

    <div id="bdqSummary" class="row g-2 mb-3"></div>

    <div id="bdqLoading" class="text-center py-4 d-none">
      <div class="spinner-border text-primary"></div>
      <div class="mt-2 text-muted">BDQ 조회 중...</div>
    </div>

    <div class="table-responsive">
      <table class="table table-sm table-striped table-hover mb-0">
        <thead>
          <tr><th style="width:60px">#</th><th>code_type</th><th>code_id</th></tr>
        </thead>
        <tbody id="bdqRows"></tbody>
      </table>
    </div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function renderSummary(data) {
  const summaryEl = document.getElementById('bdqSummary');
  const g = data.summary.groups;
  const cards = [
    { label: '전체',    value: data.summary.total, color: 'primary'   },
    { label: 'BGA',     value: g.BGA       || 0,   color: 'info'      },
    { label: '3D',      value: g['3D']     || 0,   color: 'info'      },
    { label: 'BBI',     value: g.BBI       || 0,   color: 'info'      },
    { label: 'TOPSMI',  value: g.TOPSMI    || 0,   color: 'info'      },
    { label: '기타',    value: g['기타']   || 0,   color: 'secondary' },
  ];
  summaryEl.innerHTML = cards.map(c => `
    <div class="col-6 col-md-2">
      <div class="card text-bg-${c.color}">
        <div class="card-body text-center py-2">
          <div class="small">${esc(c.label)}</div>
          <div class="h4 mb-0">${c.value}</div>
        </div>
      </div>
    </div>`).join('');
}

function renderRows(rows) {
  const rowsEl = document.getElementById('bdqRows');
  if (!rows.length) {
    rowsEl.innerHTML = '<tr><td colspan="3" class="text-center text-muted py-3">데이터 없음</td></tr>';
    return;
  }
  rowsEl.innerHTML = rows.map((r, i) => `
    <tr><td>${i + 1}</td><td>${esc(r.code_type)}</td><td>${esc(r.code_id)}</td></tr>
  `).join('');
}

async function loadBdqData() {
  const errorEl   = document.getElementById('bdqError');
  const loadingEl = document.getElementById('bdqLoading');
  const refreshBtn = document.getElementById('bdqRefreshBtn');
  const rowsEl    = document.getElementById('bdqRows');
  const summaryEl = document.getElementById('bdqSummary');

  errorEl.classList.add('d-none');
  loadingEl.classList.remove('d-none');
  refreshBtn.disabled = true;
  rowsEl.innerHTML = '';
  summaryEl.innerHTML = '';

  try {
    const res = await fetch('/api/bdq/query');
    if (!res.ok) {
      const err = await res.json().catch(() => ({detail: '알 수 없는 오류'}));
      throw new Error(err.detail || '조회 실패');
    }
    const data = await res.json();
    renderSummary(data);
    renderRows(data.rows);
    document.getElementById('bdqTable').textContent = data.table;
    document.getElementById('bdqQueriedAt').textContent = data.queried_at;
  } catch (e) {
    errorEl.textContent = '❌ ' + e.message;
    errorEl.classList.remove('d-none');
  } finally {
    loadingEl.classList.add('d-none');
    refreshBtn.disabled = false;
  }
}

document.getElementById('bdqRefreshBtn').addEventListener('click', loadBdqData);
loadBdqData();
</script>
{% endblock %}
```

- [ ] **Step 2: 페이지 라우트 테스트 재실행 — 깨지지 않았는지 확인**

Run: `pytest tests/test_bdq_router.py -v`
Expected: PASS — 5개 테스트 모두 통과 (Task 2의 `test_bdq_page_renders`도 여전히 200 + "쿼리 데이터" 텍스트 포함)

- [ ] **Step 3: 수동 브라우저 확인 (선택, 가능하면)**

서버를 띄울 수 있으면:

```bash
uvicorn app.main:app --reload
```

브라우저로 `http://localhost:8000/bdq` 접속해 다음 확인:
- 네비게이션바에 "쿼리 데이터" 메뉴 표시되고 active 상태
- 페이지 로드 직후 로딩 스피너 표시 후 사라짐
- BDQ 환경이 없는 경우 빨간 에러 배너에 "BDQ 조회 실패" 메시지 표시
- BDQ가 정상이면 요약 카드 6개 + 테이블 렌더링
- "🔄 새로고침" 버튼 클릭 시 동일 흐름 재실행

(BDQ 환경 접속 불가하면 에러 배너만 확인하면 됨 — 그 자체로 UI 동작 검증)

- [ ] **Step 4: 커밋**

```bash
git add app/templates/bdq.html
git commit -m "feat: BDQ 쿼리 데이터 페이지 UI 본 구현 (요약 카드 + 테이블)"
```

---

## Self-Review 결과

**Spec coverage:**
- 신규 라우터 `bdq.py` + 두 엔드포인트 → Task 1 + Task 2 ✓
- 신규 템플릿 `bdq.html` → Task 2(placeholder) + Task 3(본 구현) ✓
- main.py 라우터 등록 → Task 2 ✓
- base.html 네비게이션 5번째 메뉴 → Task 2 ✓
- 그룹 분류 로직 (BGA/3D/BBI/TOPSMI/기타) → Task 1 (`_classify_group` + 테스트) ✓
- 로딩/에러/성공 상태 → Task 3 ✓
- 자동 조회 + 새로고침 버튼 → Task 3 ✓
- XSS 방어 `esc()` → Task 3 ✓
- 테이블명 `_BDQ_TABLE` 노출 → Task 1 ✓

**Placeholder scan:** 없음. 모든 코드 블록은 실제 적용 가능한 완성 코드.

**Type consistency:**
- `_fetch_scrap_data` (file_generator.py 기존)
- `_BDQ_TABLE` (file_generator.py 기존)
- `query_bdq_data` (라우터 함수명, Task 1 정의)
- `_classify_group` (헬퍼 함수명, Task 1 정의)
- `active_page = 'bdq'` (페이지 라우트 + base.html에서 일치)
- 응답 키: `table`, `queried_at`, `rows`, `summary.total`, `summary.groups` — Task 1 정의 → Task 3 JS에서 동일하게 사용 ✓
