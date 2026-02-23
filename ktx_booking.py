"""
KTX 자동 예매 스크립트
코레일 승차권 예매 사이트를 Selenium으로 자동화하여 KTX를 예매합니다.

필요 패키지 설치:
    pip install selenium

사용법:
    python ktx_booking.py
"""

import time
import logging
import tempfile
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    SessionNotCreatedException,
    UnexpectedAlertPresentException,
    NoAlertPresentException,
)

# ── 로깅 설정 ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


@dataclass
class BookingConfig:
    """예매 설정"""
    # 코레일 로그인 정보
    user_id: str = "YOUR_ID"          # 코레일 회원번호 (멤버십 번호)
    password: str = "YOUR_PASSWORD"   # 비밀번호

    # 열차 조회 조건
    dep_station: str = "서울"          # 출발역
    arr_station: str = "부산"          # 도착역
    dep_date: str = "20260301"         # 출발일 (YYYYMMDD)
    dep_time: str = "08"               # 출발 희망 시각 (HH, 00~23)

    # 좌석 설정
    passenger_count: int = 1           # 어른 인원 수

    # 예매 재시도 설정
    max_attempts: int = 30             # 최대 재시도 횟수 (매진 시 반복 조회)
    retry_interval: float = 2.5        # 재시도 간격 (초)


class KTXBooker:
    """코레일 웹사이트 기반 KTX 자동 예매"""

    # ── URL (레츠코레일 - 실제 승차권 예매 사이트) ────────────────────────────
    LOGIN_URL = "https://www.letskorail.com/korail/com/login.do"
    SEARCH_URL = "https://www.letskorail.com/ebizprd/EbizPrdTicketPr21111_i1.do"

    def __init__(self, config: BookingConfig):
        self.cfg = config
        self.driver: webdriver.Chrome | None = None
        self.wait: WebDriverWait | None = None

    # ── 드라이버 초기화 ───────────────────────────────────────────────────────
    def _init_driver(self) -> None:
        opts = Options()

        # 임시 프로필 (한글 경로 크래시 방지)
        self._tmp_profile = tempfile.mkdtemp(prefix="ktx_chrome_")
        opts.add_argument(f"--user-data-dir={self._tmp_profile}")

        # 안정성 옵션
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        opts.add_experimental_option("useAutomationExtension", False)

        log.info("Chrome 시작 중...")
        try:
            self.driver = webdriver.Chrome(options=opts)
        except SessionNotCreatedException as exc:
            log.error(
                "Chrome 세션 생성 실패: %s\n\n"
                "[해결 방법]\n"
                "1. Chrome 을 최신 버전으로 업데이트하세요.\n"
                "2. pip install -U selenium  (4.25 이상 권장)\n"
                "3. 실행 중인 Chrome 창을 모두 닫고 다시 시도하세요.\n",
                exc,
            )
            raise

        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        self.wait = WebDriverWait(self.driver, 15)
        log.info("Chrome 초기화 완료")

    # ── alert 처리 ────────────────────────────────────────────────────────────
    def _dismiss_alert(self) -> str | None:
        """alert 이 있으면 수락하고 메시지를 반환, 없으면 None"""
        try:
            alert = self.driver.switch_to.alert
            msg = alert.text
            alert.accept()
            return msg
        except NoAlertPresentException:
            return None

    # ── 로그인 ────────────────────────────────────────────────────────────────
    def login(self) -> None:
        log.info("로그인 페이지 이동: %s", self.LOGIN_URL)
        self.driver.get(self.LOGIN_URL)
        time.sleep(2)

        # 회원번호 로그인 탭 (기본)
        id_input = self.wait.until(
            EC.presence_of_element_located((By.ID, "txtMember"))
        )
        id_input.clear()
        id_input.send_keys(self.cfg.user_id)

        pw_input = self.driver.find_element(By.ID, "txtPwd")
        pw_input.clear()
        pw_input.send_keys(self.cfg.password)

        # 로그인 버튼 클릭
        login_btn = self.driver.find_element(
            By.CSS_SELECTOR, 'img[alt="확인"]'
        )
        login_btn.click()
        time.sleep(2)

        # alert 확인 (로그인 실패 시 알림)
        alert_msg = self._dismiss_alert()
        if alert_msg:
            raise RuntimeError(f"로그인 실패: {alert_msg}")

        # 로그아웃 버튼 존재 여부로 성공 확인
        try:
            self.driver.find_element(
                By.CSS_SELECTOR, 'a[onclick*="logout"]'
            )
            log.info("로그인 성공")
        except NoSuchElementException:
            raise RuntimeError("로그인 실패: 아이디/비밀번호를 확인하세요.")

    # ── 열차 조회 페이지 이동 및 조건 입력 ───────────────────────────────────
    def search_trains(self) -> None:
        log.info("승차권 예매 페이지로 이동")
        self.driver.get(self.SEARCH_URL)
        time.sleep(2)

        # 출발역 입력
        dep_input = self.wait.until(
            EC.presence_of_element_located((By.ID, "txtGoStart"))
        )
        self.driver.execute_script("arguments[0].value = '';", dep_input)
        dep_input.send_keys(self.cfg.dep_station)

        # 도착역 입력
        arr_input = self.driver.find_element(By.ID, "txtGoEnd")
        self.driver.execute_script("arguments[0].value = '';", arr_input)
        arr_input.send_keys(self.cfg.arr_station)

        # 날짜 설정 (년/월/일)
        year = self.cfg.dep_date[:4]
        month = self.cfg.dep_date[4:6]
        day = self.cfg.dep_date[6:8]

        try:
            Select(self.driver.find_element(By.NAME, "selGoYear")).select_by_value(year)
        except (NoSuchElementException, Exception):
            log.warning("년도 선택 실패, 기본값 유지")

        try:
            Select(self.driver.find_element(By.NAME, "selGoMonth")).select_by_value(month)
        except (NoSuchElementException, Exception):
            log.warning("월 선택 실패, 기본값 유지")

        try:
            Select(self.driver.find_element(By.NAME, "selGoDay")).select_by_value(day)
        except (NoSuchElementException, Exception):
            log.warning("일 선택 실패, 기본값 유지")

        # 시간 설정
        try:
            Select(self.driver.find_element(By.NAME, "selGoHour")).select_by_value(
                self.cfg.dep_time
            )
        except (NoSuchElementException, Exception):
            log.warning("시간 선택 실패, 기본값 유지")

        # 인원 설정
        try:
            Select(self.driver.find_element(By.ID, "peop01")).select_by_value(
                str(self.cfg.passenger_count)
            )
        except (NoSuchElementException, Exception):
            pass

        log.info(
            "조회 조건: %s → %s  %s-%s-%s  %s시 이후  %d명",
            self.cfg.dep_station, self.cfg.arr_station,
            year, month, day, self.cfg.dep_time,
            self.cfg.passenger_count,
        )

        # 조회 버튼 클릭
        try:
            search_btn = self.driver.find_element(
                By.CSS_SELECTOR, 'img[alt="승차권예매"]'
            )
            search_btn.click()
        except NoSuchElementException:
            # 대체 셀렉터
            search_btn = self.driver.find_element(
                By.CSS_SELECTOR, "#center > form > div > p > a"
            )
            search_btn.click()

        time.sleep(3)
        self._dismiss_alert()  # 조회 후 나올 수 있는 alert 처리
        log.info("열차 조회 완료")

    # ── 예매 가능 열차 선택 ───────────────────────────────────────────────────
    def find_and_reserve(self) -> bool:
        """
        조회 결과 테이블에서 예매 가능한 열차를 찾아 클릭합니다.
        #tableResult > tbody > tr 구조 (레츠코레일 예매 결과 페이지)

        열 구조:
          td[1]: 열차종류   td[2]: 열차번호   td[3]: 출발역/시각
          td[4]: 도착역/시각 td[5]: 특실       td[6]: 일반실
          ...

        예매 가능: img[alt="예약하기"] 또는 icon_apm_bl.gif / icon_apm_rd.gif
        매진:      "매진" 텍스트
        """
        rows = self.driver.find_elements(
            By.CSS_SELECTOR, "#tableResult > tbody > tr"
        )
        if not rows:
            # 대체 셀렉터
            rows = self.driver.find_elements(
                By.CSS_SELECTOR, "#divResult > table.tbl_h tr"
            )

        if not rows:
            log.info("조회 결과 없음")
            return False

        for i, row in enumerate(rows):
            try:
                # 일반실 예매 버튼 (td:nth-child(6))
                coach_cell = row.find_element(By.CSS_SELECTOR, "td:nth-child(6)")
                reserve_btn = None

                # 방법 1: img[alt="예약하기"] 버튼
                try:
                    reserve_btn = coach_cell.find_element(
                        By.CSS_SELECTOR, 'img[alt="예약하기"]'
                    )
                except NoSuchElementException:
                    pass

                # 방법 2: 예매 가능 아이콘 (파란색/빨간색)
                if not reserve_btn:
                    try:
                        reserve_btn = coach_cell.find_element(
                            By.CSS_SELECTOR,
                            'img[src*="icon_apm_bl.gif"], img[src*="icon_apm_rd.gif"]'
                        )
                    except NoSuchElementException:
                        continue

                # 출발 시각 확인
                try:
                    dep_info = row.find_element(By.CSS_SELECTOR, "td:nth-child(3)").text.strip()
                except NoSuchElementException:
                    dep_info = f"row {i}"

                log.info("예매 가능 열차 발견: %s", dep_info)

                # 클릭 (a 태그 안에 img가 있는 구조)
                parent_link = reserve_btn.find_element(By.XPATH, "./ancestor::a")
                self.driver.execute_script("arguments[0].click();", parent_link)
                time.sleep(2)

                # 팝업/모달 처리 (이미 선점된 경우 등)
                self._handle_post_click()
                return True

            except NoSuchElementException:
                continue

        log.info("예매 가능한 열차 없음 (매진)")
        return False

    def _handle_post_click(self) -> None:
        """예매 클릭 후 팝업/iframe 모달 처리"""
        # alert 처리
        alert_msg = self._dismiss_alert()
        if alert_msg:
            log.warning("알림: %s", alert_msg)

        # iframe 모달 ("예매 계속 진행하기" 버튼)
        try:
            iframe = self.driver.find_element(By.ID, "embeded-modal-traininfo")
            self.driver.switch_to.frame(iframe)
            continue_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_blue_ang"))
            )
            continue_btn.click()
            self.driver.switch_to.default_content()
            log.info("팝업 '예매 계속 진행' 클릭")
            time.sleep(1)
        except (NoSuchElementException, TimeoutException):
            self.driver.switch_to.default_content()

    # ── 재조회 (새로고침) ─────────────────────────────────────────────────────
    def refresh_search(self) -> None:
        """조회 결과 페이지에서 재조회 버튼 클릭 (또는 페이지 새로고침)"""
        try:
            # .btn_inq 클래스의 조회 버튼 클릭
            inq_btn = self.driver.find_element(By.CSS_SELECTOR, ".btn_inq > a")
            inq_btn.click()
        except NoSuchElementException:
            # 조회 버튼을 못 찾으면 페이지 새로고침
            self.driver.refresh()
        time.sleep(2)
        self._dismiss_alert()

    # ── 메인 실행 흐름 ────────────────────────────────────────────────────────
    def run(self) -> None:
        self._init_driver()
        try:
            self.login()
            self.search_trains()

            for attempt in range(1, self.cfg.max_attempts + 1):
                log.info("── 예매 시도 %d / %d ──", attempt, self.cfg.max_attempts)

                try:
                    if self.find_and_reserve():
                        log.info(
                            "예매 성공! 20분 이내에 결제를 완료하세요.\n"
                            "브라우저에서 직접 결제를 진행해주세요."
                        )
                        input("결제 완료 후 Enter 키를 누르세요...")
                        break
                except UnexpectedAlertPresentException:
                    self._dismiss_alert()

                if attempt < self.cfg.max_attempts:
                    log.info("%.1f초 후 재시도...", self.cfg.retry_interval)
                    time.sleep(self.cfg.retry_interval)
                    self.refresh_search()
            else:
                log.warning("최대 재시도 횟수(%d) 도달. 예매 실패.", self.cfg.max_attempts)

        finally:
            log.info("브라우저를 닫지 않습니다. 직접 확인 후 종료하세요.")


# ── 진입점 ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    config = BookingConfig(
        user_id="YOUR_ID",        # ← 코레일 회원번호
        password="YOUR_PASSWORD", # ← 비밀번호
        dep_station="서울",        # 출발역
        arr_station="부산",        # 도착역
        dep_date="20260301",       # YYYYMMDD
        dep_time="08",             # HH (00~23)
        passenger_count=1,
        max_attempts=30,
        retry_interval=2.5,        # 초 (너무 빠르면 계정 차단 위험)
    )

    booker = KTXBooker(config)
    booker.run()
