# 설비 상태 카드 그리드 설계

## Goal

대시보드에서 다수의 설비(수십 대)의 연결 상태와 배포 상태를 한눈에 파악할 수 있도록 라인별 카드 그리드 뷰를 추가한다.

## Architecture

기존 대시보드(운영 모드 카드) 안에 설비 카드 그리드 섹션을 삽입한다. 새 페이지나 새 API 엔드포인트는 만들지 않는다. `Equipment` 모델에 `group_name` 컬럼을 추가해 라인/공정 단위 그룹핑을 지원하고, 기존 `/api/deploy/status/today` 응답에 `group_name`을 포함시킨다.

## Tech Stack

- FastAPI + SQLAlchemy (기존)
- Jinja2 + Bootstrap 5 (기존)
- 경량 마이그레이션 (기존 `_LIGHTWEIGHT_MIGRATIONS` 패턴)

---

## 변경 범위

### 1. 데이터 모델 — `app/models.py`

`Equipment`에 `group_name` 컬럼 추가:

```python
group_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
```

### 2. DB 마이그레이션 — `app/database.py`

`_LIGHTWEIGHT_MIGRATIONS`에 항목 추가:

```python
"equipment": [
    ...
    ("group_name", "VARCHAR(50)"),
]
```

### 3. 설비 API — `app/routers/equipment.py`

`EquipmentCreate` / `EquipmentUpdate` 스키마에 `group_name: Optional[str] = None` 추가.

`GET /api/equipment` 응답에 `group_name` 포함.

### 4. 배포 상태 API — `app/routers/deploy.py`

`/api/deploy/status/today`의 `equipment_status` 배열 항목에 `group_name` 필드 추가:

```json
{
  "id": 1,
  "name": "설비-A1",
  "group_name": "A라인",
  "ip": "192.168.1.10",
  "file_YieldConvDef": {...},
  "file_RejectMapFile": {...}
}
```

`group_name`이 null 또는 빈 문자열이면 `"기타"`로 반환한다.

### 5. 설비 관리 모달 — `app/templates/equipment.html`

추가/수정 모달에 "라인/그룹" 입력란 추가 (선택 입력):

```html
<div class="col-md-6">
  <label class="form-label">라인/그룹 (선택)</label>
  <input type="text" class="form-control" id="f_group" placeholder="예: A라인">
</div>
```

`saveEquipment()` payload에 `group_name` 포함. `openEditModal()`에서 `f_group` 값 설정.

### 6. 대시보드 카드 그리드 — `app/templates/dashboard.html`

운영 모드 카드 안, 요약 숫자 카드(`summaryCards`) 바로 아래에 설비 카드 그리드 삽입:

```html
<div id="equipmentCardGrid" class="mb-4"></div>
```

`refreshStatus()` 호출 시 `equipment_status` 데이터로 카드 그리드를 렌더링한다.

**카드 레이아웃:**

```
[A라인]                                      ← 섹션 헤더 (group_name)
┌──────────┐ ┌──────────┐ ┌──────────┐
│ 설비-A1   │ │ 설비-A2   │ │ 설비-A3   │
│ ● 정상    │ │ ✗ 실패    │ │ ○ 미확인  │   ← 연결 상태
│ ✓ 배포   │ │ ✗ 실패    │ │ — 미배포  │   ← 배포 상태
└──────────┘ └──────────┘ └──────────┘

[B라인]
...
```

**카드 컬럼:** `col-6 col-sm-4 col-md-3 col-xl-2` (화면 너비에 따라 한 줄 2~6개)

**연결 상태 표시:**
- `ok` → 초록 테두리 + `● 정상`
- `failed` → 빨강 테두리 + `✗ 실패`
- `unknown` / null → 회색 테두리 + `○ 미확인`

**배포 상태 표시 (YieldConvDef + RejectMapFile 합산):**
- 둘 다 success → `✓ 배포완료`
- 하나라도 failed → `✗ 배포실패`
- 둘 다 pending/null → `— 미배포`
- 한쪽만 success → `△ 일부배포`

**인터랙션:** 카드는 순수 상태 표시 전용. 클릭/버튼 없음.

**갱신:** `refreshStatus()` (30초 자동 갱신) 호출 시 함께 갱신.

---

## 그룹 정렬

`group_name` 기준 오름차순 정렬. `group_name`이 없는 설비는 "기타" 그룹으로 맨 뒤에 배치.

## 테스트 계획

- `group_name` 없는 설비 → "기타" 섹션 렌더링 확인
- `group_name` 있는 설비 → 해당 섹션 헤더 아래 카드 렌더링 확인
- 연결 상태별 카드 테두리 색상 확인 (ok/failed/unknown)
- 배포 상태별 뱃지 확인 (완료/실패/미배포/일부)
- 설비 수 증감 시 카드 그리드 동적 갱신 확인
- 모달에서 `group_name` 저장/수정 후 API 응답 반영 확인
