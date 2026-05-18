# BDQ 쿼리 데이터 확인 페이지 설계

## Goal

`mos_tsp_smi.gpm_tp_be_mng_sbl_scrap_code` 테이블에서 조회된 원본 데이터를 UI에서 직접 확인할 수 있도록 네비게이션바에 신규 "쿼리 데이터" 페이지를 추가한다. 파일 생성 시 사용되는 BDQ 데이터가 의도한 테이블과 일치하는지 진단·검증할 수 있게 한다.

## Architecture

신규 라우터(`app/routers/bdq.py`)와 신규 템플릿(`app/templates/bdq.html`)을 추가하고, 기존 `app/services/file_generator.py`의 `_fetch_scrap_data()`를 재사용한다. 페이지는 빈 셸로 렌더되고 JS가 `/api/bdq/query`를 호출해 데이터를 받아 렌더링한다(`dashboard.html`과 동일한 패턴).

## Tech Stack

- FastAPI + Jinja2 (기존)
- Bootstrap 5 (기존)
- 순수 fetch + JS DOM 렌더링 (기존 패턴)
- `_fetch_scrap_data()` 재사용 (`app/services/file_generator.py`)

---

## 변경 범위

### 1. 신규 라우터 — `app/routers/bdq.py`

두 개의 엔드포인트:

- `GET /bdq` → `bdq.html` 페이지 렌더 (active_page='bdq')
- `GET /api/bdq/query` → JSON 응답

**JSON 응답 (성공, 200):**

```json
{
  "table": "mos_tsp_smi.gpm_tp_be_mng_sbl_scrap_code",
  "queried_at": "2026-05-18 14:30:15",
  "rows": [
    {"code_type": "BGA001", "code_id": "12"},
    {"code_type": "3D_M01", "code_id": "5"}
  ],
  "summary": {
    "total": 142,
    "groups": {
      "BGA": 30,
      "3D": 25,
      "BBI": 20,
      "TOPSMI": 15,
      "기타": 52
    }
  }
}
```

**JSON 응답 (실패, 503):**

```json
{ "detail": "BDQ 조회 실패: 로그인 실패 또는 데이터 없음" }
```

**그룹 분류 로직:** `code_type` prefix 기준으로 `_fetch_scrap_data()`가 반환한 DataFrame을 분류 — `generate_yield_condef()`에서 쓰는 정렬 우선순위와 동일하게:
- `code_type.startswith("BGA")` → BGA
- `code_type.startswith("3D")` → 3D
- `code_type.startswith("BBI")` → BBI
- `code_type.startswith("TOPSMI")` → TOPSMI
- 그 외 → 기타

**테이블명 상수 참조:** `file_generator._BDQ_TABLE`을 import해 응답의 `table` 필드에 그대로 노출.

**캐싱 안 함:** 매 호출마다 `_fetch_scrap_data()`를 신규 실행해 BDQ 세션을 갱신하고 최신 데이터를 반환.

### 2. 신규 템플릿 — `app/templates/bdq.html`

`base.html`을 상속. 페이지 구성:

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
async function loadBdqData() {
  const errorEl = document.getElementById('bdqError');
  const loadingEl = document.getElementById('bdqLoading');
  const refreshBtn = document.getElementById('bdqRefreshBtn');
  const rowsEl = document.getElementById('bdqRows');
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

function renderSummary(data) {
  const summaryEl = document.getElementById('bdqSummary');
  const groups = data.summary.groups;
  const cards = [
    { label: '전체', value: data.summary.total, color: 'primary' },
    { label: 'BGA', value: groups.BGA || 0, color: 'info' },
    { label: '3D', value: groups['3D'] || 0, color: 'info' },
    { label: 'BBI', value: groups.BBI || 0, color: 'info' },
    { label: 'TOPSMI', value: groups.TOPSMI || 0, color: 'info' },
    { label: '기타', value: groups['기타'] || 0, color: 'secondary' },
  ];
  summaryEl.innerHTML = cards.map(c => `
    <div class="col-6 col-md-2">
      <div class="card text-bg-${c.color}">
        <div class="card-body text-center py-2">
          <div class="small">${c.label}</div>
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

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

document.getElementById('bdqRefreshBtn').addEventListener('click', loadBdqData);
loadBdqData();
</script>
{% endblock %}
```

**페이지 진입 시점에 자동 조회**(`loadBdqData()` 즉시 실행). 새로고침 버튼은 동일 함수 재호출.

**XSS 방어:** `esc()` 헬퍼로 모든 셀 값 escape.

### 3. 라우터 등록 — `app/main.py`

```python
from app.routers import equipment, file_templates, deploy, logs, files, bdq
...
app.include_router(bdq.router)
```

### 4. 네비게이션 메뉴 — `app/templates/base.html`

기존 4개 메뉴 옆에 5번째 추가:

```html
<li class="nav-item">
  <a class="nav-link {% if active_page == 'bdq' %}active{% endif %}" href="/bdq">쿼리 데이터</a>
</li>
```

---

## 페이지 동작

**로드 시:**
1. 빈 셸 렌더 → 스피너 + "BDQ 조회 중..." 표시 → 새로고침 버튼 disabled
2. `fetch('/api/bdq/query')` 호출
3. 성공: 요약 카드 6개 + 테이블 렌더, 헤더에 테이블명/조회시각 표시
4. 실패: 빨간 경고 배너에 에러 메시지, 새로고침 버튼 활성 복귀

**새로고침 버튼 클릭:**
- 위 흐름 그대로 재실행

## 에러 처리

- BDQ 로그인 실패 → 503 응답 → UI 경고 배너
- BDQ 조회 결과 빈 DataFrame → 503 응답 (`_fetch_scrap_data()`가 None 반환) → 경고 배너
- 그 외 예외 → 500 응답 → 경고 배너

## 테스트 계획

- 정상 응답 시 `rows` 배열과 `summary.groups`의 합이 `summary.total`과 일치 확인
- `table` 필드가 `file_generator._BDQ_TABLE` 상수값과 일치 확인
- 그룹 분류: BGA/3D/BBI/TOPSMI prefix가 올바르게 분류되는지 확인
- BDQ 실패 시(monkeypatch로 `_fetch_scrap_data` → None) 503 응답 확인
- 페이지 `/bdq` 응답에 nav active 상태 반영 확인
