# 설비 카드 그리드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대시보드에 라인별 설비 상태 카드 그리드를 추가해 수십 대의 연결/배포 상태를 한눈에 파악할 수 있게 한다.

**Architecture:** Equipment 모델에 `group_name` 컬럼을 추가하고, 기존 경량 마이그레이션 패턴으로 기존 DB에 반영한다. `/api/deploy/status/today` 응답에 `group_name`과 `last_ping_status`를 추가하고, 대시보드 JS에서 그룹별 카드 그리드를 렌더링한다.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Jinja2, Bootstrap 5, pytest

---

## 파일 구조

| 파일 | 변경 내용 |
|------|-----------|
| `app/models.py` | Equipment에 `group_name` 컬럼 추가 |
| `app/database.py` | `_LIGHTWEIGHT_MIGRATIONS`에 `group_name` 항목 추가 |
| `app/routers/equipment.py` | 스키마 + `_serialize` 에 `group_name` 추가 |
| `app/routers/deploy.py` | `today_status` 응답에 `group_name`, `last_ping_status` 추가 |
| `app/templates/equipment.html` | 모달에 그룹 입력란 추가 |
| `app/templates/dashboard.html` | 설비 카드 그리드 섹션 추가 |
| `tests/test_card_grid.py` | Task 1~3 자동화 테스트 |

---

## Task 1: group_name 컬럼 추가 (모델 + 마이그레이션)

**Files:**
- Modify: `app/models.py:22-39`
- Modify: `app/database.py:51-59`
- Create: `tests/test_card_grid.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_card_grid.py` 파일 생성:

```python
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
python -m pytest tests/test_card_grid.py -v
```

Expected: `FAILED` — `Equipment` 생성 시 `group_name` 키워드 인자를 받지 못하거나 속성이 없음.

- [ ] **Step 3: Equipment 모델에 group_name 컬럼 추가**

`app/models.py` 39번 줄 (`last_ping_ms` 컬럼) 다음에 추가:

```python
    group_name:     Mapped[str | None] = mapped_column(String(50), nullable=True)   # 라인/그룹명 (예: A라인)
```

최종 Equipment 모델 하단부:
```python
    last_ping_at:      Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_ping_status:  Mapped[str]  = mapped_column(String(20), default="unknown")
    last_ping_message: Mapped[str]  = mapped_column(Text, default="")
    last_ping_ms:      Mapped[int | None] = mapped_column(Integer, nullable=True)
    group_name:        Mapped[str | None] = mapped_column(String(50), nullable=True)

    deploy_logs: Mapped[list["DeployLog"]] = relationship("DeployLog", back_populates="equipment")
```

- [ ] **Step 4: DB 마이그레이션에 group_name 항목 추가**

`app/database.py`의 `_LIGHTWEIGHT_MIGRATIONS` 딕셔너리:

```python
_LIGHTWEIGHT_MIGRATIONS = {
    "equipment": [
        ("last_ping_at",      "DATETIME"),
        ("last_ping_status",  "VARCHAR(20) NOT NULL DEFAULT 'unknown'"),
        ("last_ping_message", "TEXT NOT NULL DEFAULT ''"),
        ("last_ping_ms",      "INTEGER"),
        ("group_name",        "VARCHAR(50)"),                              # 라인/그룹명
    ],
}
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/test_card_grid.py -v
```

Expected: `PASSED` 2개.

- [ ] **Step 6: 커밋**

```bash
git add app/models.py app/database.py tests/test_card_grid.py
git commit -m "feat: Equipment에 group_name 컬럼 추가 및 마이그레이션"
```

---

## Task 2: Equipment API 스키마 + 직렬화 함수 갱신

**Files:**
- Modify: `app/routers/equipment.py:49-91`
- Modify: `tests/test_card_grid.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_card_grid.py` 에 추가:

```python
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
python -m pytest tests/test_card_grid.py::test_serialize_includes_group_name -v
```

Expected: `FAILED` — `result["group_name"]` KeyError 또는 값 불일치.

- [ ] **Step 3: `_serialize` 함수에 group_name 추가**

`app/routers/equipment.py`의 `_serialize` 함수 (현재 49-66번 줄):

```python
def _serialize(e: Equipment) -> dict:
    """Equipment ORM 객체를 JSON 직렬화 가능한 딕셔너리로 변환한다."""
    return {
        "id":                e.id,
        "name":              e.name,
        "ip":                e.ip,
        "port":              e.port,
        "ftp_user":          e.ftp_user,
        "use_sftp":          e.use_sftp,
        "is_active":         e.is_active,
        "description":       e.description,
        "group_name":        e.group_name,
        "created_at":        e.created_at.strftime("%Y-%m-%d %H:%M"),
        "last_ping_at":      e.last_ping_at.strftime("%Y-%m-%d %H:%M:%S") if e.last_ping_at else None,
        "last_ping_status":  e.last_ping_status or "unknown",
        "last_ping_message": e.last_ping_message or "",
        "last_ping_ms":      e.last_ping_ms,
    }
```

- [ ] **Step 4: `EquipmentCreate`와 `EquipmentUpdate` 스키마에 group_name 추가**

`app/routers/equipment.py`의 스키마 클래스 (71-91번 줄):

```python
class EquipmentCreate(BaseModel):
    """설비 추가 시 클라이언트가 보내는 JSON 형식"""
    name:        str
    ip:          str
    port:        int        = 21
    ftp_user:    str        = ""
    ftp_pass:    str        = ""
    use_sftp:    bool       = False
    description: str        = ""
    group_name:  str | None = None


class EquipmentUpdate(BaseModel):
    """설비 수정 시 클라이언트가 보내는 JSON 형식 (모든 필드 선택적)"""
    name:        str | None  = None
    ip:          str | None  = None
    port:        int | None  = None
    ftp_user:    str | None  = None
    ftp_pass:    str | None  = None
    use_sftp:    bool | None = None
    is_active:   bool | None = None
    description: str | None  = None
    group_name:  str | None  = None
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/test_card_grid.py -v
```

Expected: `PASSED` 4개.

- [ ] **Step 6: 커밋**

```bash
git add app/routers/equipment.py tests/test_card_grid.py
git commit -m "feat: Equipment API 스키마 및 직렬화 함수에 group_name 추가"
```

---

## Task 3: 배포 상태 API에 group_name + last_ping_status 추가

**Files:**
- Modify: `app/routers/deploy.py:111-122`
- Modify: `tests/test_card_grid.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_card_grid.py` 에 추가:

```python
def test_today_status_includes_group_name_and_ping(db):
    from app.routers.deploy import today_status
    eq = Equipment(
        name="테스트-E1", ip="192.168.1.5",
        group_name="E라인", last_ping_status="ok",
    )
    db.add(eq)
    db.commit()

    result = today_status(db=db)
    entry = next(e for e in result["equipment_status"] if e["name"] == "테스트-E1")
    assert entry["group_name"] == "E라인"
    assert entry["last_ping_status"] == "ok"


def test_today_status_group_name_fallback_to_other(db):
    from app.routers.deploy import today_status
    eq = Equipment(name="테스트-F1", ip="192.168.1.6")
    db.add(eq)
    db.commit()

    result = today_status(db=db)
    entry = next(e for e in result["equipment_status"] if e["name"] == "테스트-F1")
    assert entry["group_name"] == "기타"
    assert entry["last_ping_status"] == "unknown"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
python -m pytest tests/test_card_grid.py::test_today_status_includes_group_name_and_ping -v
```

Expected: `FAILED` — `entry["group_name"]` KeyError.

- [ ] **Step 3: today_status 응답에 group_name, last_ping_status 추가**

`app/routers/deploy.py`의 `equipment_status.append(...)` 블록 (111-122번 줄):

```python
    equipment_status = []
    for eq in equipment_list:
        eq_logs = deploy_map.get(eq.id, {})
        equipment_status.append({
            "id":                 eq.id,
            "name":               eq.name,
            "ip":                 eq.ip,
            "group_name":         eq.group_name or "기타",
            "last_ping_status":   eq.last_ping_status or "unknown",
            "file_YieldConvDef":  eq_logs.get("YieldConvDef",  {"status": "pending"}),
            "file_RejectMapFile": eq_logs.get("RejectMapFile", {"status": "pending"}),
        })
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_card_grid.py -v
```

Expected: `PASSED` 6개.

- [ ] **Step 5: 커밋**

```bash
git add app/routers/deploy.py tests/test_card_grid.py
git commit -m "feat: 배포 상태 API 응답에 group_name, last_ping_status 추가"
```

---

## Task 4: 설비 관리 모달에 그룹 입력란 추가

**Files:**
- Modify: `app/templates/equipment.html`

자동화 테스트 없음 (UI 전용). 수동 확인 절차는 Step 3에 포함.

- [ ] **Step 1: 모달 HTML에 group_name 입력란 추가**

`app/templates/equipment.html`의 모달 `row g-3` 안, `f_desc` 필드 바로 위에 추가:

```html
          <div class="col-md-6">
            <label class="form-label">라인/그룹 <span class="text-muted small">(선택)</span></label>
            <input type="text" class="form-control" id="f_group" placeholder="예: A라인">
          </div>
```

`f_desc` 컬럼을 `col-md-6`으로 변경:

```html
          <div class="col-md-6">
            <label class="form-label">설명 (선택)</label>
            <input type="text" class="form-control" id="f_desc" placeholder="설비 설명">
          </div>
```

- [ ] **Step 2: JS 함수에 group_name 연동**

`openAddModal()` 함수에서 초기화 줄을 수정:

```javascript
  function openAddModal() {
    document.getElementById('modalTitle').textContent = '설비 추가';
    document.getElementById('editId').value = '';
    ['f_name','f_ip','f_user','f_pass','f_desc','f_group'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('f_port').value = 21;
    document.getElementById('f_sftp').checked = false;
    modal.show();
  }
```

`openEditModal()` 함수에서 `f_group` 값 설정 추가:

```javascript
  function openEditModal(id) {
    fetch(`/api/equipment`)
      .then(r => r.json())
      .then(list => {
        const e = list.find(x => x.id === id);
        if (!e) return;
        document.getElementById('modalTitle').textContent = '설비 수정';
        document.getElementById('editId').value = e.id;
        document.getElementById('f_name').value = e.name;
        document.getElementById('f_ip').value = e.ip;
        document.getElementById('f_port').value = e.port;
        document.getElementById('f_user').value = e.ftp_user;
        document.getElementById('f_pass').value = '';
        document.getElementById('f_sftp').checked = e.use_sftp;
        document.getElementById('f_desc').value = e.description;
        document.getElementById('f_group').value = e.group_name || '';
        modal.show();
      });
  }
```

`saveEquipment()` payload에 `group_name` 추가:

```javascript
    const payload = {
      name: document.getElementById('f_name').value.trim(),
      ip: document.getElementById('f_ip').value.trim(),
      port: parseInt(document.getElementById('f_port').value),
      ftp_user: document.getElementById('f_user').value.trim(),
      ftp_pass: document.getElementById('f_pass').value,
      use_sftp: document.getElementById('f_sftp').checked,
      description: document.getElementById('f_desc').value.trim(),
      group_name: document.getElementById('f_group').value.trim() || null,
    };
```

- [ ] **Step 3: 수동 확인**

앱 실행 후:
1. 설비 추가 모달 열기 → "라인/그룹" 입력란이 표시되는지 확인
2. `A라인` 입력 후 저장 → `GET /api/equipment` 응답에 `"group_name": "A라인"` 확인
3. 설비 수정 모달 열기 → `f_group`에 기존 값이 채워지는지 확인
4. 그룹 비워두고 저장 → `group_name: null` 로 저장되는지 확인

- [ ] **Step 4: 커밋**

```bash
git add app/templates/equipment.html
git commit -m "feat: 설비 모달에 라인/그룹 입력란 추가"
```

---

## Task 5: 대시보드 설비 카드 그리드 추가

**Files:**
- Modify: `app/templates/dashboard.html`

자동화 테스트 없음 (UI 전용). 수동 확인 절차는 Step 3에 포함.

- [ ] **Step 1: 카드 그리드 컨테이너 추가**

`app/templates/dashboard.html`의 `summaryCards` div 닫는 태그 다음, `파일 생성 현황` 카드 바로 위에 추가:

```html
    <div id="equipmentCardGrid" class="mb-4"></div>
```

위치 기준 — 현재 79번 줄 `<div class="row g-3 mb-4" id="summaryCards">` 블록이 끝나는 지점 (112번 줄 `</div>`) 직후:

```html
    </div>  <!-- /summaryCards -->

    <div id="equipmentCardGrid" class="mb-4"></div>

    <div class="card mb-3">
      <div class="card-header fw-semibold">파일 생성 현황 (오늘)</div>
```

- [ ] **Step 2: 카드 그리드 렌더링 함수 추가**

`app/templates/dashboard.html`의 `<script>` 블록 상단(기존 함수들 위)에 추가:

```javascript
  function _pingBorderClass(status) {
    if (status === 'ok') return 'border-success';
    if (status === 'failed') return 'border-danger';
    return 'border-secondary';
  }

  function _pingLabel(status) {
    if (status === 'ok') return '<span class="text-success small">● 정상</span>';
    if (status === 'failed') return '<span class="text-danger small">✗ 실패</span>';
    return '<span class="text-secondary small">○ 미확인</span>';
  }

  function _deployLabel(ycd, rmf) {
    const y = (ycd && ycd.status) || 'pending';
    const r = (rmf && rmf.status) || 'pending';
    if (y === 'success' && r === 'success')
      return '<span class="badge bg-success">✓ 완료</span>';
    if (y === 'failed' || r === 'failed')
      return '<span class="badge bg-danger">✗ 실패</span>';
    if (y === 'success' || r === 'success')
      return '<span class="badge bg-warning text-dark">△ 일부</span>';
    return '<span class="badge bg-secondary">— 미배포</span>';
  }

  function renderEquipmentCards(equipmentStatus) {
    const grid = document.getElementById('equipmentCardGrid');
    if (!equipmentStatus || equipmentStatus.length === 0) {
      grid.innerHTML = '';
      return;
    }

    // group_name 기준으로 그룹핑
    const groups = {};
    equipmentStatus.forEach(e => {
      const key = e.group_name || '기타';
      if (!groups[key]) groups[key] = [];
      groups[key].push(e);
    });

    // 알파벳순 정렬, '기타'는 맨 뒤
    const sortedKeys = Object.keys(groups).sort((a, b) => {
      if (a === '기타') return 1;
      if (b === '기타') return -1;
      return a.localeCompare(b, 'ko');
    });

    grid.innerHTML = sortedKeys.map(group => `
      <div class="mb-3">
        <div class="text-muted small fw-semibold mb-2 border-bottom pb-1">${esc(group)}</div>
        <div class="row g-2">
          ${groups[group].map(e => `
            <div class="col-6 col-sm-4 col-md-3 col-xl-2">
              <div class="card h-100 border-2 ${_pingBorderClass(e.last_ping_status)}">
                <div class="card-body p-2 text-center">
                  <div class="fw-semibold small text-truncate" title="${esc(e.name)}">${esc(e.name)}</div>
                  <div class="mt-1">${_pingLabel(e.last_ping_status)}</div>
                  <div class="mt-1">${_deployLabel(e.file_YieldConvDef, e.file_RejectMapFile)}</div>
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');
  }
```

- [ ] **Step 3: `refreshStatus()` 함수 마지막에 카드 그리드 갱신 호출 추가**

`app/templates/dashboard.html`의 `refreshStatus()` 함수 안, `document.getElementById('deployTable').innerHTML = depRows;` 바로 다음에 추가:

```javascript
        renderEquipmentCards(data.equipment_status);
```

최종 `refreshStatus()` 끝 부분:

```javascript
        document.getElementById('deployTable').innerHTML = depRows;
        renderEquipmentCards(data.equipment_status);
      })
      .catch(() => showAlert('상태 조회 실패', 'danger'));
  }
```

- [ ] **Step 4: 수동 확인**

앱 실행 후 대시보드 접속:
1. `A라인`으로 설정된 설비들이 "A라인" 섹션 헤더 아래 카드로 표시되는지 확인
2. `group_name` 없는 설비는 "기타" 섹션에 표시되는지 확인
3. 연결 정상 설비: 초록 테두리 확인
4. 연결 실패 설비: 빨간 테두리 확인
5. 30초 후 카드 그리드 자동 갱신 확인
6. 화면 폭을 줄였을 때 카드가 2열 이하로 줄어드는지 확인 (반응형)

- [ ] **Step 5: 전체 테스트 실행**

```bash
python -m pytest tests/ -v
```

Expected: 기존 6개 + 새 6개 = `12 passed`.

- [ ] **Step 6: 커밋**

```bash
git add app/templates/dashboard.html
git commit -m "feat: 대시보드에 라인별 설비 카드 그리드 추가"
```

---

## 완료 후

```bash
git push -u origin claude/equipment-deployment-dashboard-u79Zx
```
