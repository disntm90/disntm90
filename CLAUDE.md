# Claude Code — 프로젝트 지침

## 주식 종목 분석

종목 분석 요청 시 (`XXX 분석해줘`, `XXX 종목 분석`, 등) 반드시 아래 파일을 적용:

**→ `/home/user/disntm90/stock-analysis-template.md` 참고**

### 시각화 파일 저장 규칙
- 파일명: `dashboard-{TICKER}.html` (소문자)
  - 예: `dashboard-slnh.html`, `dashboard-nvda.html`, `dashboard-tsla.html`
- 저장 위치: `/home/user/disntm90/`
- **덮어쓰기 금지**: 같은 티커가 이미 존재하면 `dashboard-{TICKER}-v2.html` 형식으로 버전 증가
- gh-pages 배포 시: GitHub API(`mcp__github__create_or_update_file`)로 `{TICKER}.html` 경로에 push
  - URL: `https://disntm90.github.io/disntm90/{ticker}.html`

### 분석 순서
1. 웹 검색으로 실시간 가격·지표 수집
2. `stock-analysis-template.md` 7개 섹션 순서대로 분석 작성
3. 분석 완료 후 인터랙티브 React 대시보드 생성 → `dashboard-{TICKER}.html`
4. GitHub API로 gh-pages에 배포
5. 접속 URL 유저에게 안내

### 언어 & 포맷
- 한국어, 맞춤법 확인
- 모바일 단일 컬럼 (화면 분할 금지)
- 차트: Chart.js (CDN), 다크 테마
