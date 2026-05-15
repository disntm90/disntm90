# Bug Fixes Design: 설비 배포 대시보드

**날짜:** 2026-05-15
**브랜치:** claude/equipment-deployment-dashboard-u79Zx

## 범위

4개의 버그/기능 결함을 수정한다.

---

## Bug 1 — 설비 수정 시 비밀번호 초기화

### 문제

`openEditModal()`에서 비밀번호 입력란이 항상 빈칸으로 초기화된다.
사용자가 다른 필드만 수정하고 저장해도 `ftp_pass: ""`가 서버로 전송되어 기존 비밀번호가 삭제된다.
서버(`update_equipment()`)도 빈 문자열을 그대로 업데이트한다.

### 해결

- **`app/routers/equipment.py`**: `update_equipment()`에서 `ftp_pass`가 빈 문자열(`""`)인 경우 해당 필드를 업데이트하지 않는다. (`exclude_none=True` 로직 확장)
- **`app/templates/equipment.html`**: 비밀번호 입력란 placeholder를 `"변경하지 않으려면 비워두세요"`로 변경한다.

### 변경 파일

- `app/routers/equipment.py` — `update_equipment()` 함수
- `app/templates/equipment.html` — 비밀번호 입력란 placeholder

---

## Bug 2 — 연결 테스트 후 점검 시각 미갱신

### 문제

`POST /api/equipment/{id}/test-connection` HTMX 요청이 `#ping-{id}` 셀(배지)만 교체한다.
같은 행의 `최근 점검` 시각 칸은 갱신되지 않아 이전 시각이 그대로 표시된다.

### 해결

- **`app/templates/_equipment_row.html`**: 연결 테스트 버튼의 HTMX 속성을 행 전체를 교체하도록 변경한다.
  - `hx-target="#ping-{id}"` → `hx-target="#row-{id}"`
  - `hx-swap="innerHTML"` → `hx-swap="outerHTML"`
- **`app/routers/equipment.py`**: `test_equipment_connection()`에서 HTMX 요청 시 `_render_ping()` 대신 `_render_row()`를 반환한다.

### 변경 파일

- `app/templates/_equipment_row.html` — 연결 테스트 버튼 HTMX 속성
- `app/routers/equipment.py` — `test_equipment_connection()` 함수

---

## Bug 3 — FileTemplate UI와 파일 생성 단절

### 문제

`/templates` 페이지에서 `RejectMapFile` 템플릿을 수정·저장해도
`file_generator.py`는 `data/static_xml_template.txt` 파일을 직접 읽어
DB의 `FileTemplate` 테이블을 전혀 사용하지 않는다.
사용자가 UI에서 변경해도 실제 파일 생성에 반영되지 않는다.

### 해결

- **`app/database.py` `init_db()`**: 앱 시작 시 `FileTemplate` 테이블에 `file_type="RejectMapFile"` 행이 없으면 `STATIC_XML_TEMPLATE` 내용으로 자동 시드한다. (최초 1회)
- **`app/services/file_generator.py` `generate_reject_mapfile()`**: `_ensure_template()`(파일 기반) 대신 DB `FileTemplate` 테이블에서 `file_type="RejectMapFile"`, `is_active=True` 인 행을 조회하고 없으면 `STATIC_XML_TEMPLATE` 상수로 폴백한다.
- **`app/templates/file_templates.html`**: 템플릿 저장 시 "파일 생성에 반영됩니다" 안내 문구를 추가한다.

### 변경 파일

- `app/database.py` — `init_db()` 함수 (시드 로직 추가)
- `app/services/file_generator.py` — `generate_reject_mapfile()` 함수
- `app/templates/file_templates.html` — 안내 문구

---

## Bug 4 — `.bak` 파일이 생성 파일 목록에 표시

### 문제

`generate_reject_mapfile()`이 기존 파일을 `.bak`으로 백업한 후 덮어쓴다.
`/api/files/generated` API가 디렉토리 내 모든 파일을 반환하므로 `.bak` 파일도 목록에 포함된다.

### 해결

- **`app/routers/files.py` `list_generated_files()`**: `p.suffix == ".bak"` 인 파일을 목록에서 제외한다.

### 변경 파일

- `app/routers/files.py` — `list_generated_files()` 함수

---

## 비기능 요구사항

- 기존 API 스펙 변경 없음 (하위 호환 유지)
- DB 스키마 변경 없음 (`FileTemplate` 테이블은 이미 존재)
- 각 수정은 독립적으로 적용 가능
