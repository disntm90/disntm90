# Claude Code — 프로젝트 지침

## 주식 종목 분석

종목 분석 요청 시 (`XXX 분석해줘`, `XXX 종목 분석`, 등) 반드시 아래 파일을 적용:

**→ `/home/user/disntm90/stock-analysis-template.md` 참고**

### 시각화 파일 저장 규칙
- 파일명: `dashboard-{TICKER}-{YYYYMMDD}.html` (소문자, 날짜 포함)
  - 예: `dashboard-slnh-20260511.html`, `dashboard-nvda-20260511.html`
  - 날짜는 분석 요청 당일 기준 (currentDate 사용)
- 저장 위치: `/home/user/disntm90/`
- **덮어쓰기 금지**: 같은 티커+날짜 파일이 이미 존재하면 `dashboard-{TICKER}-{YYYYMMDD}-v2.html` 형식으로 버전 증가
- gh-pages 배포 시: GitHub API(`mcp__github__create_or_update_file`)로 `{ticker}-{YYYYMMDD}.html` 경로에 push
  - URL: `https://disntm90.github.io/disntm90/{ticker}-{YYYYMMDD}.html`
  - **배포하면 인덱스에 자동 반영** (별도 작업 불필요)

### 열람 인덱스 (자동 업데이트)
- URL: **`https://disntm90.github.io/disntm90/`**
- `index.html`이 GitHub Contents API로 `{ticker}-{YYYYMMDD}.html` 파일을 자동 감지
- 신규 종목을 gh-pages에 배포하면 인덱스에 즉시 반영됨 (수동 편집 불필요)
- 인덱스 로컬 파일: `/home/user/disntm90/index.html`

### 대시보드 필수 요소
각 대시보드 헤더에 반드시 포함:
```jsx
<a href="https://disntm90.github.io/disntm90/" style={{...}}>← 목록으로</a>
```

### 분석 순서
1. 웹 검색으로 실시간 가격·지표 수집
2. `stock-analysis-template.md` 7개 섹션 순서대로 분석 작성
3. 분석 완료 후 인터랙티브 React 대시보드 생성 → `dashboard-{TICKER}-{YYYYMMDD}.html`
4. GitHub API로 gh-pages에 배포 → 인덱스 자동 반영
5. 개별 대시보드 URL + 인덱스 URL 유저에게 안내

### 언어 & 포맷
- 한국어, 맞춤법 확인
- 모바일 단일 컬럼 (화면 분할 금지)
- 차트: Chart.js (CDN), 다크 테마
