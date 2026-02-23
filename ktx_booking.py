"""
KTX 자동 예매 스크립트
Korail 공식 웹사이트(www.letskorail.com)를 Selenium으로 자동화하여 KTX를 예매합니다.

필요 패키지 설치:
    pip install selenium

사용법:
    python ktx_booking.py
"""

import time
import logging
import subprocess
import shutil
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    SessionNotCreatedException,
)

# ── 로깅 설정 ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── 역 코드 매핑 ──────────────────────────────────────────────────────────────
STATION_CODE: dict[str, str] = {
    "서울": "0001",
    "용산": "0002",
    "영등포": "0003",
    "광명": "0004",
    "수원": "0005",
    "천안아산": "0010",
    "오송": "0015",
    "대전": "0020",
    "김천구미": "0025",
    "동대구": "0030",
    "경주": "0035",
    "울산": "0040",
    "부산": "0045",
    "신경주": "0035",
    "광주송정": "0060",
    "목포": "0065",
    "전주": "0055",
    "익산": "0050",
}


@dataclass
class BookingConfig:
    """예매 설정"""
    # Korail 로그인 정보
    user_id: str = "YOUR_ID"          # 코레일 회원 아이디
    password: str = "YOUR_PASSWORD"   # 코레일 비밀번호

    # 열차 조회 조건
    dep_station: str = "서울"          # 출발역
    arr_station: str = "부산"          # 도착역
    dep_date: str = "20260301"         # 출발일 (YYYYMMDD)
    dep_time: str = "080000"           # 출발 희망 시각 이후 (HHMMSS)

    # 좌석 설정
    passenger_count: int = 1           # 인원 수 (최대 9)
    seat_type: str = "일반실"          # 일반실 | 특실

    # 예매 재시도 설정
    max_attempts: int = 20             # 최대 재시도 횟수 (매진 시 반복 조회)
    retry_interval: float = 3.0        # 재시도 간격 (초)

    # 결제 설정
    auto_pay: bool = False             # True: 자동 결제 / False: 결제 화면 직전 중단


class KTXBooker:
    """Korail 웹사이트 기반 KTX 자동 예매 클래스"""

    BASE_URL = "https://www.letskorail.com"
    LOGIN_URL = f"{BASE_URL}/korail/com/login/loginForm.do"
    SEARCH_URL = f"{BASE_URL}/ebizprd/EbizPrdTicketpr21100W.do"

    def __init__(self, config: BookingConfig):
        self.cfg = config
        self.driver: webdriver.Chrome | None = None
        self.wait: WebDriverWait | None = None

    # ── 드라이버 초기화 ───────────────────────────────────────────────────────
    def _init_driver(self) -> None:
        opts = Options()

        # ── 안정성 옵션 (Windows Chrome 145+ 호환) ────────────────────────
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--remote-debugging-port=0")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--disable-blink-features=AutomationControlled")

        # 자동화 탐지 우회
        opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        opts.add_experimental_option("useAutomationExtension", False)

        # 헤드리스 실행을 원하면 아래 주석 해제
        # opts.add_argument("--headless=new")

        # ── ChromeDriver 자동 탐색 ────────────────────────────────────────
        # Selenium 4.6+ 에 내장된 SeleniumManager 가 Chrome 버전에 맞는
        # ChromeDriver 를 자동으로 다운로드·관리하므로 webdriver-manager 불필요
        try:
            self.driver = webdriver.Chrome(options=opts)
        except SessionNotCreatedException as exc:
            log.error(
                "Chrome 세션 생성 실패: %s\n\n"
                "[해결 방법]\n"
                "1. Chrome 을 최신 버전으로 업데이트하세요.\n"
                "2. pip install -U selenium  (4.25 이상 권장)\n"
                "3. 백신/방화벽이 chromedriver 를 차단하는지 확인하세요.\n",
                exc,
            )
            raise

        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        self.wait = WebDriverWait(self.driver, 15)
        log.info("Chrome 드라이버 초기화 완료 (Chrome %s)", self._chrome_version())

    def _chrome_version(self) -> str:
        """현재 연결된 Chrome 버전 반환"""
        try:
            caps = self.driver.capabilities
            return caps.get("browserVersion", caps.get("version", "unknown"))
        except Exception:
            return "unknown"

    # ── 로그인 ────────────────────────────────────────────────────────────────
    def login(self) -> None:
        log.info("로그인 시도: %s", self.cfg.user_id)
        self.driver.get(self.LOGIN_URL)
        time.sleep(1.5)

        id_input = self.wait.until(EC.presence_of_element_located((By.ID, "txtMember")))
        id_input.clear()
        id_input.send_keys(self.cfg.user_id)

        pw_input = self.driver.find_element(By.ID, "txtPwd")
        pw_input.clear()
        pw_input.send_keys(self.cfg.password)
        pw_input.send_keys(Keys.RETURN)
        time.sleep(2)

        # 로그인 성공 여부 확인 (URL 변화 또는 오류 메시지)
        if "loginForm" in self.driver.current_url:
            raise RuntimeError("로그인 실패: 아이디/비밀번호를 확인하세요.")
        log.info("로그인 성공")

    # ── 열차 조회 페이지 이동 및 조건 입력 ───────────────────────────────────
    def go_to_search(self) -> None:
        log.info("열차 조회 페이지로 이동")
        self.driver.get(self.SEARCH_URL)
        time.sleep(1.5)

        self._set_station("txtGoStation", self.cfg.dep_station)
        self._set_station("txtArvStation", self.cfg.arr_station)
        self._set_date()
        self._set_time()
        self._set_passengers()

    def _set_station(self, field_id: str, station_name: str) -> None:
        el = self.wait.until(EC.presence_of_element_located((By.ID, field_id)))
        el.clear()
        el.send_keys(station_name)
        time.sleep(0.5)

    def _set_date(self) -> None:
        date_el = self.driver.find_element(By.ID, "txtGoDate")
        self.driver.execute_script(
            "arguments[0].value = arguments[1];", date_el, self.cfg.dep_date
        )

    def _set_time(self) -> None:
        hour = self.cfg.dep_time[:2]
        try:
            time_sel = Select(self.driver.find_element(By.ID, "selGoHour"))
            time_sel.select_by_value(hour)
        except NoSuchElementException:
            log.warning("시간 선택 요소를 찾지 못했습니다. 기본값 유지")

    def _set_passengers(self) -> None:
        try:
            pax_sel = Select(self.driver.find_element(By.ID, "txtPsgFlg_1"))
            pax_sel.select_by_value(str(self.cfg.passenger_count))
        except NoSuchElementException:
            log.warning("인원 선택 요소를 찾지 못했습니다. 기본값(1명) 유지")

    # ── 조회 실행 ─────────────────────────────────────────────────────────────
    def search_trains(self) -> None:
        log.info(
            "열차 조회: %s → %s  %s  %s 이후",
            self.cfg.dep_station,
            self.cfg.arr_station,
            self.cfg.dep_date,
            self.cfg.dep_time[:2] + "시",
        )
        search_btn = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, "//input[@value='조회하기']"))
        )
        search_btn.click()
        time.sleep(2)

    # ── 예매 가능 열차 선택 ───────────────────────────────────────────────────
    def select_train(self) -> bool:
        """
        조회 결과에서 예매 가능한 첫 번째 KTX 열차를 선택합니다.
        성공하면 True, 매진이면 False를 반환합니다.
        """
        rows = self.driver.find_elements(By.XPATH, "//table[contains(@class,'tbl_info')]//tr[@class!='']")
        if not rows:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table.tbl_info > tbody > tr")

        for row in rows:
            try:
                # 열차 유형 확인 (KTX만 선택)
                train_type = row.find_element(By.XPATH, ".//td[1]").text.strip()
                if "KTX" not in train_type:
                    continue

                # 좌석 종류에 따라 예매 버튼 열 결정
                col_idx = 7 if self.cfg.seat_type == "특실" else 8
                book_btn = row.find_element(
                    By.XPATH,
                    f".//td[{col_idx}]//a[contains(text(),'예매')]",
                )
                dep_time = row.find_element(By.XPATH, ".//td[3]").text.strip()
                log.info("예매 가능 열차 발견: %s %s", train_type, dep_time)
                book_btn.click()
                time.sleep(2)
                return True
            except NoSuchElementException:
                continue

        log.info("예매 가능한 KTX 열차 없음 (매진 또는 조회 결과 없음)")
        return False

    # ── 좌석 선택 ─────────────────────────────────────────────────────────────
    def select_seat(self) -> None:
        """자동 배정 좌석 또는 창가 우선 선택"""
        try:
            # '자동 배정' 라디오 버튼 클릭
            auto_seat = self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//input[@type='radio' and @value='000']")
                )
            )
            auto_seat.click()
            log.info("좌석 자동 배정 선택")
        except TimeoutException:
            log.warning("좌석 선택 화면을 찾지 못했습니다. 다음 단계로 진행")

        time.sleep(1)

        # 다음 단계 진행 버튼 클릭
        try:
            next_btn = self.driver.find_element(
                By.XPATH, "//a[contains(text(),'다음')]"
            )
            next_btn.click()
        except NoSuchElementException:
            log.warning("'다음' 버튼을 찾지 못했습니다.")
        time.sleep(2)

    # ── 결제 ──────────────────────────────────────────────────────────────────
    def proceed_payment(self) -> None:
        if not self.cfg.auto_pay:
            log.info(
                "auto_pay=False 설정 → 결제 화면 직전에서 중단합니다.\n"
                "브라우저를 확인하여 수동으로 결제를 진행하세요."
            )
            input("결제를 완료한 후 Enter 키를 누르세요...")
            return

        # 결제 수단: 신용카드 선택 (기본값)
        try:
            card_radio = self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//input[@type='radio' and contains(@id, 'card')]")
                )
            )
            card_radio.click()
        except TimeoutException:
            log.warning("결제 수단 선택 요소를 찾지 못했습니다.")

        # 결제 확인 버튼 클릭
        pay_btn = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(text(),'결제하기')] | //input[@value='결제하기']")
            )
        )
        pay_btn.click()
        log.info("결제 요청 완료")
        time.sleep(3)

    # ── 예매 완료 확인 ────────────────────────────────────────────────────────
    def confirm_booking(self) -> bool:
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(text(),'예약이 완료')]")
                )
            )
            log.info("예매 완료!")
            return True
        except TimeoutException:
            log.warning("예매 완료 메시지를 확인하지 못했습니다.")
            return False

    # ── 메인 실행 흐름 ────────────────────────────────────────────────────────
    def run(self) -> None:
        self._init_driver()
        try:
            self.login()
            self.go_to_search()
            self.search_trains()

            for attempt in range(1, self.cfg.max_attempts + 1):
                log.info("예매 시도 %d / %d", attempt, self.cfg.max_attempts)

                if self.select_train():
                    self.select_seat()
                    self.proceed_payment()
                    self.confirm_booking()
                    break
                else:
                    if attempt < self.cfg.max_attempts:
                        log.info("%.1f초 후 재시도...", self.cfg.retry_interval)
                        time.sleep(self.cfg.retry_interval)
                        self.driver.refresh()
                        time.sleep(2)
            else:
                log.warning("최대 재시도 횟수 도달. 예매에 실패했습니다.")
        finally:
            log.info("브라우저를 닫지 않습니다. 확인 후 직접 종료하세요.")
            # self.driver.quit()  # 자동으로 닫으려면 주석 해제


# ── 진입점 ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    config = BookingConfig(
        user_id="YOUR_ID",        # ← 여기에 코레일 아이디 입력
        password="YOUR_PASSWORD", # ← 여기에 비밀번호 입력
        dep_station="서울",
        arr_station="부산",
        dep_date="20260301",      # YYYYMMDD 형식
        dep_time="080000",        # HH 이후 열차 조회
        passenger_count=1,
        seat_type="일반실",       # 일반실 | 특실
        max_attempts=20,
        retry_interval=3.0,
        auto_pay=False,           # True로 바꾸면 자동 결제 시도
    )

    booker = KTXBooker(config)
    booker.run()
