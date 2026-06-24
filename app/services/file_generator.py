"""
file_generator.py — XML 파일 생성 서비스

생성 대상:
  YieldConvDef.xml  — bigdataquery DB 조회 결과를 정렬해 XML로 작성
  RejectMapFile.xml — 동일 조회 결과 + primecode.csv 매핑 + 정적 템플릿 조합

외부 진입점:
  generate_yield_condef()  — YieldConvDef 단독 생성
  generate_reject_mapfile() — RejectMapFile 단독 생성
  generate_all_files()     — 두 파일 한 번에 생성 (DB 조회는 1회만)
"""

import io            # StringIO — sys.stdin 교체용
import logging
import os
import sys           # sys.stdin / sys.__stdin__ 교체용
import xml.etree.ElementTree as ET  # XML 생성·파싱 표준 라이브러리
from pathlib import Path
from typing import Optional

import numpy as np    # 조건별 컬럼 값 일괄 설정 (np.select)
import pandas as pd   # DB 조회 결과 데이터프레임 처리
from dotenv import load_dotenv  # .env를 여기서도 직접 로드 (import 순서 무관하게 보장)

load_dotenv()  # BDQ_USER / BDQ_PASS가 os.getenv()보다 먼저 로드되도록

from app.database import SessionLocal
from app.models import GenerateLog
from config import GENERATED_DIR, DATA_DIR

logger = logging.getLogger(__name__)

# ── 보조 파일 경로 ────────────────────────────────────────────────
PRIMECODE_CSV  = DATA_DIR / "primecode.csv"            # code_type → prime_code 매핑 테이블
TEMPLATE_FILE  = DATA_DIR / "static_xml_template.txt"  # RejectMapFile 정적 뼈대
DEFAULT_PRIMECODE = "1"   # primecode.csv에 없는 code_type에 적용할 기본값

# ── 배포 대상 파일 목록 (단일 소스) ──────────────────────────────
# (파일타입, 파일명, 설비 내 배포 경로)
# deployer.py가 이 목록을 import해서 사용하므로, 경로 변경 시 여기만 수정한다.
OUTPUT_FILES = [
    ("YieldConvDef",  "YieldConvDef.xml",  "C:/Icos"),
    ("RejectMapFile", "RejectMapFile.xml",  "C:/Handler/SamsungAutomation/Configuration"),
]

# ── bigdataquery SQL ──────────────────────────────────────────────
# ICOS 벤더 기준의 불량 코드 목록 조회
_BDQ_TABLE = "mos_tsp_smi.gpm_tp_be_mng_sbl_scrap_code"
_BDQ_QUERY = f"""
    SELECT code_type, code_id, code_desc
    FROM {_BDQ_TABLE}
    WHERE vendor_name = 'ICOS'
"""

# ── RejectMapFile 정적 XML 뼈대 ───────────────────────────────────
# {DYNAMIC_SCRAP_MAPS} 자리에 DB 조회 결과로 생성된 <ScrapMap .../> 행들이 삽입된다.
# 이 내용은 data/static_xml_template.txt 파일로도 저장되며, 파일이 없으면 자동 생성된다.
STATIC_XML_TEMPLATE = """\
<?xml version="1.0" encoding="utf-8"?>
<RejectCodeMapSettings>
<Line Code="YTS3">
    <PrimaryScrapCode>
        <ScrapCode Name="M/K" ID="1"/>
        <ScrapCode Name="PKG" ID="2"/>
        <ScrapCode Name="Ball" ID="3"/>
        <ScrapCode Name="PCB" ID="4"/>
        <ScrapCode Name="ENCAP" ID="5"/>
        <ScrapCode Name="Lead" ID="6"/>
        <ScrapCode Name="Chip" ID="7"/>
        <ScrapCode Name="1차 Reject Total" ID="100"/>
        <ScrapCode Name="Prime-Bin5" ID="105"/>
        <ScrapCode Name="Prime-Bin6" ID="106"/>
        <ScrapCode Name="Prime-Bin7" ID="107"/>
        <ScrapCode Name="Prime-Bin8" ID="108"/>
        <ScrapCode Name="Prime-Bin9+공손" ID="109"/>
        <ScrapCode Name="Mark" ID="210"/>
        <ScrapCode Name="Pitch(Bent)" ID="264"/>
        <ScrapCode Name="Coplanarity" ID="265"/>
        <ScrapCode Name="Foot Flake/Blurr(Tin)" ID="266"/>
    </PrimaryScrapCode>
    <SecondaryScrapCode>
{DYNAMIC_SECONDARY_SCRAP_CODES}
    </SecondaryScrapCode>
    <ScrapMaps>
{DYNAMIC_SCRAP_MAPS}
    </ScrapMaps>
</Line>
</RejectCodeMapSettings>
"""


# ──────────────────────────────────────────────────────────────────
# bigdataquery 자동 로그인 + DB 조회
# ──────────────────────────────────────────────────────────────────

# bigdataquery 세션 활성 여부를 모듈 전역 플래그로 관리
# True  = 로그인 성공 상태 → getData() 바로 호출 가능
# False = 로그인 안 됨 or 세션 만료 → getData() 전 재로그인 필요
_bdq_session_active = False


def _bdq_login() -> bool:
    """
    .env의 BDQ_USER / BDQ_PASS 로 bigdataquery login() 자동 실행.

    sys.stdin을 StringIO로 교체해 login()이 읽는 순간 자격증명이 입력된다.
    login() 완료 후에는 빈 StringIO로 복원한다 — SSH/터미널 세션이 닫혀
    원본 stdin 파이프가 끊긴 환경에서 [WinError 233]이 발생하는 것을 방지.
    서버 프로세스는 대화형 stdin이 불필요하므로 빈 StringIO로 충분하다.
    """
    global _bdq_session_active

    try:
        import bigdataquery as bdq
    except ImportError:
        logger.error("bigdataquery 패키지가 설치되어 있지 않습니다.")
        return False

    user = os.getenv("BDQ_USER", "")
    pw   = os.getenv("BDQ_PASS", "")

    if not user or not pw:
        logger.error("BDQ_USER 또는 BDQ_PASS 환경변수가 설정되지 않았습니다.")
        return False

    account_info = io.StringIO(f"{user}\n{pw}")
    try:
        sys.stdin = account_info
        bdq.login()
        _bdq_session_active = True
        logger.info(f"bigdataquery 로그인 성공 (user: {user})")
        return True
    except Exception as exc:
        logger.error(f"bigdataquery 로그인 실패: {exc}")
        _bdq_session_active = False
        return False
    finally:
        account_info.close()
        # 빈 StringIO로 복원 — 원본 stdin(sys.__stdin__)이 터미널 세션 종료로
        # 파이프가 끊긴 경우 [WinError 233]을 유발하므로 사용하지 않는다.
        sys.stdin = io.StringIO("")


def _fetch_scrap_data() -> Optional[pd.DataFrame]:
    """
    DB에서 불량 코드 목록을 조회한다.

    호출될 때마다 재로그인 후 bdq.getData()를 실행해 상위 서버의 최신 데이터를 반영한다.
    세션 만료로 인한 캐시 데이터 반환을 방지하기 위해 매 조회 전 로그인을 갱신한다.
    반환값: 성공 시 DataFrame, 실패 시 None
    """
    try:
        import bigdataquery as bdq
    except ImportError:
        logger.error("bigdataquery 패키지가 설치되어 있지 않습니다.")
        return None

    user = os.getenv("BDQ_USER", "")
    if not user:
        logger.error("BDQ_USER 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return None

    # 매 조회 전 로그인 갱신 — 세션 만료 시 bigdataquery가 캐시 데이터를 반환하는 문제 방지
    if not _bdq_login():
        logger.error("bigdataquery 로그인 실패로 DB 조회를 중단합니다.")
        return None

    logger.info(f"getData 호출: user_name='{user}', table='{_BDQ_TABLE}', condition='vendor_name=ICOS'")
    logger.debug(f"getData query:\n{_BDQ_QUERY.strip()}")
    try:
        df = bdq.getData(param=_BDQ_QUERY, user_name=user)
    except Exception as exc:
        logger.error(f"DB 조회 실패: {exc}")
        return None

    if df.empty:
        logger.warning("조회된 데이터가 없습니다.")
        return None

    logger.info(f"getData 완료: {len(df)}행 조회 (table='{_BDQ_TABLE}')")

    return df.copy()


# ──────────────────────────────────────────────────────────────────
# XML 무결성 검증
# ──────────────────────────────────────────────────────────────────

def _validate_xml(path: Path, *, expected_root: str, min_items: int = 1) -> tuple[bool, str]:
    """
    생성된 XML 파일의 기본 무결성을 검사한다.

    검사 항목:
      1. well-formed 여부 (XML 파싱 가능한지)
      2. 루트 태그가 expected_root 와 일치하는지
      3. 전체 요소 수가 min_items 이상인지

    반환: (성공 여부, 메시지)
    """
    try:
        tree = ET.parse(str(path))         # 파일을 파싱 — 실패 시 ParseError 발생
    except ET.ParseError as exc:
        return False, f"XML 파싱 실패: {exc}"

    root = tree.getroot()
    if root.tag != expected_root:
        return False, f"루트 태그 불일치 (expected={expected_root}, actual={root.tag})"

    items = list(root.iter())              # 모든 하위 요소를 평탄하게 수집
    if len(items) < min_items:
        return False, f"항목 수 부족 ({len(items)} < {min_items})"

    return True, f"검증 OK (요소 {len(items)}개)"


# ──────────────────────────────────────────────────────────────────
# YieldConvDef.xml 생성
# ──────────────────────────────────────────────────────────────────

def generate_yield_condef(triggered_by: str = "scheduler") -> dict:
    """
    YieldConvDef.xml 을 생성한다.

    호출될 때마다 DB를 새로 조회해 최신 데이터를 반영한다.
    반환: {"file_type", "filename", "status", ("error" or "message")}
    """
    filename = "YieldConvDef.xml"
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    df = _fetch_scrap_data()
    if df is None:
        return {"file_type": "YieldConvDef", "filename": filename,
                "status": "failed", "error": "DB 조회 실패 또는 데이터 없음"}

    df = df.copy()

    # 대소문자/공백 차이로 같은 값이 다르게 취급되지 않도록 먼저 정규화한 뒤 중복 제거
    df["code_type"] = df["code_type"].astype(str).str.strip().str.upper()
    df = df.drop_duplicates(subset=["code_type"])

    # ── 정렬 우선순위 설정 ────────────────────────────────────────
    # code_type 접두사로 정렬 그룹을 부여한다.
    # np.select(조건 리스트, 값 리스트, default) 는 조건을 순서대로 확인해
    # 첫 번째 True인 조건의 값을 행별로 적용한다.
    conditions = [
        df["code_type"].str.startswith("BGA",    na=False),   # BGA 계열 → 1순위
        df["code_type"].str.startswith("3D",     na=False),   # 3D  계열 → 2순위
        df["code_type"].str.startswith("BBI",    na=False),   # BBI 계열 → 3순위
        df["code_type"].str.startswith("TOPSMI", na=False),   # TOPSMI 계열 → 4순위
    ]
    df["sort_priority"] = np.select(conditions, [1, 2, 3, 4], default=5)
    df.sort_values(by=["sort_priority", "code_id"], inplace=True)

    # ── XML 트리 구성 ─────────────────────────────────────────────
    root       = ET.Element("YieldDefinitions")
    yield_table = ET.SubElement(root, "YieldTable")
    title       = ET.SubElement(yield_table, "Title")
    title.text  = "Ranked Rejects"
    ranked_def  = ET.SubElement(yield_table, "RankedYieldDefinition")

    # 정렬된 code_type 값을 <Yield> 태그로 추가
    for code_type in df["code_type"]:
        ET.SubElement(ranked_def, "Yield").text = str(code_type).upper()

    ET.indent(root, space="  ")    # 들여쓰기 적용 (가독성)
    output_path = GENERATED_DIR / filename
    ET.ElementTree(root).write(str(output_path), encoding="utf-8", xml_declaration=True)

    # ── 무결성 검증 ───────────────────────────────────────────────
    valid, validation_msg = _validate_xml(output_path, expected_root="YieldDefinitions", min_items=3)
    if not valid:
        logger.error(f"YieldConvDef 무결성 검증 실패: {validation_msg}")
        return {"file_type": "YieldConvDef", "filename": filename,
                "status": "failed", "error": validation_msg}

    logger.info(f"YieldConvDef 생성 완료: {output_path} ({len(df)}개 항목, table={_BDQ_TABLE}, {validation_msg})")
    return {"file_type": "YieldConvDef", "filename": filename,
            "status": "success", "message": validation_msg}


# ──────────────────────────────────────────────────────────────────
# RejectMapFile.xml 생성
# ──────────────────────────────────────────────────────────────────

def _load_primecode_map() -> dict:
    """
    primecode.csv 를 읽어 {code_type(대문자): prime_code} 딕셔너리를 반환한다.
    파일이 없거나 읽기 실패 시 빈 딕셔너리를 반환하고 DEFAULT_PRIMECODE 로 대체된다.
    """
    if not PRIMECODE_CSV.exists():
        logger.warning(f"primecode.csv 없음 → 기본값({DEFAULT_PRIMECODE}) 사용: {PRIMECODE_CSV}")
        return {}

    # 사내 환경에서 cp949(EUC-KR)를 먼저 시도한 뒤, UTF-8으로 재시도
    for encoding in ("cp949", "utf-8"):
        try:
            df = pd.read_csv(PRIMECODE_CSV, dtype=str, encoding=encoding)
            # key를 대문자로 통일 (DB 조회값과 대소문자 불일치 방지)
            mapping = {str(k).upper(): v for k, v in zip(df["code_type"], df["primecode"])}
            logger.info(f"primecode 매핑 로드 완료 – {len(mapping)}건 ({encoding})")
            return mapping
        except UnicodeDecodeError:
            continue   # 다음 인코딩 시도
        except Exception as exc:
            logger.error(f"primecode.csv 파싱 오류: {exc}")
            return {}

    logger.error("primecode.csv 인코딩 감지 실패 (cp949/utf-8 모두 실패)")
    return {}



def _xml_attr(val) -> str:
    """XML attribute value escape — &, <, >, " 를 엔티티로 변환."""
    return (str(val)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def generate_reject_mapfile(triggered_by: str = "scheduler") -> dict:
    """
    RejectMapFile.xml 을 생성한다.

    호출될 때마다 DB를 새로 조회해 최신 데이터를 반영한다.
    생성 과정:
      1. primecode.csv 로 code_type → prime_code 매핑 로드
      2. code_type 기준으로 정규화 + 중복 제거 (SecondaryScrapCode, ScrapMaps 공통)
      3. SecondaryScrapCode: code_id 오름차순 정렬 → <ScrapCode ID=.. Name=..> 생성
      4. ScrapMaps: prime_code 매핑 + 정렬 → <ScrapMap ...> 생성
      5. 정적 템플릿의 placeholder 두 곳에 삽입
      6. XML 무결성 검증
    """
    filename = "RejectMapFile.xml"
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    prime_map = _load_primecode_map()

    df_raw = _fetch_scrap_data()
    if df_raw is None:
        return {"file_type": "RejectMapFile", "filename": filename,
                "status": "failed", "error": "DB 조회 실패 또는 데이터 없음"}

    # 대소문자/공백 차이로 같은 값이 다르게 취급되지 않도록 먼저 정규화한 뒤
    # code_type 기준으로 중복 제거 (SecondaryScrapCode와 ScrapMaps가 동일한 행 집합을 사용)
    df_raw = df_raw.copy()
    df_raw["code_type"] = df_raw["code_type"].astype(str).str.strip().str.upper()
    df_raw["code_id"]   = df_raw["code_id"].astype(str).str.strip().str.upper()
    df = df_raw.drop_duplicates(subset=["code_type"]).copy()

    # ── SecondaryScrapCode 동적 행 생성 ───────────────────────────
    df_secondary = df.sort_values(by=["code_id"])
    secondary_lines = [
        f'\t\t<ScrapCode ID="{_xml_attr(str(row.code_id).upper())}" Name="{_xml_attr(str(row.code_desc).upper())}"/>'
        for row in df_secondary.itertuples(index=False)
    ]
    secondary_xml = "\n".join(secondary_lines)

    # ── ScrapMaps 동적 행 생성 ────────────────────────────────────
    df["prime_code"] = df["code_type"].astype(str).str.upper().map(prime_map).fillna(DEFAULT_PRIMECODE)
    df.sort_values(by=["prime_code", "code_id"], inplace=True)

    scrap_map_lines = [
        f'\t\t<ScrapMap RejectCode="{_xml_attr(str(row.code_type).upper())}" PrimeCode="{_xml_attr(str(row.prime_code).upper())}" SecondaryCode="{_xml_attr(str(row.code_id).upper())}"/>'
        for row in df.itertuples(index=False)
    ]
    scrap_maps_xml = "\n".join(scrap_map_lines)

    # 정적 템플릿에 동적 부분 두 곳 삽입
    template  = STATIC_XML_TEMPLATE
    final_xml = (template
                 .replace("{DYNAMIC_SECONDARY_SCRAP_CODES}", secondary_xml)
                 .replace("{DYNAMIC_SCRAP_MAPS}", scrap_maps_xml))

    # 기존 파일이 있으면 .bak으로 백업 후 덮어쓰기
    output_path = GENERATED_DIR / filename
    if output_path.exists():
        backup = output_path.with_suffix(".bak")
        try:
            os.replace(str(output_path), str(backup))  # 원자적 이름 변경
        except Exception as exc:
            logger.warning(f"백업 실패 (계속 진행): {exc}")

    output_path.write_text(final_xml, encoding="utf-8")

    # ── 무결성 검증 ───────────────────────────────────────────────
    valid, validation_msg = _validate_xml(
        output_path, expected_root="RejectCodeMapSettings", min_items=3
    )
    if not valid:
        logger.error(f"RejectMapFile 무결성 검증 실패: {validation_msg}")
        return {"file_type": "RejectMapFile", "filename": filename,
                "status": "failed", "error": validation_msg}

    logger.info(f"RejectMapFile 생성 완료: {output_path} ({len(df)}개 항목, table={_BDQ_TABLE}, {validation_msg})")
    return {"file_type": "RejectMapFile", "filename": filename,
            "status": "success", "message": validation_msg}


# ──────────────────────────────────────────────────────────────────
# 외부 진입점 — 스케줄러 / API에서 호출
# ──────────────────────────────────────────────────────────────────

def generate_all_files(triggered_by: str = "scheduler") -> list[dict]:
    """
    YieldConvDef 와 RejectMapFile 을 한 번에 생성한다.

    각 파일 생성 함수가 독립적으로 DB를 조회해 최신 데이터를 반영한다.
    결과는 GenerateLog 테이블에 기록된다.
    """
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    generators = [
        ("YieldConvDef",  "YieldConvDef.xml",  generate_yield_condef),
        ("RejectMapFile", "RejectMapFile.xml",  generate_reject_mapfile),
    ]

    results = []
    db = SessionLocal()
    try:
        for file_type, filename, fn in generators:
            result = fn(triggered_by=triggered_by)

            # GenerateLog 테이블에 결과 기록
            status  = result["status"]
            message = (result.get("error", "")
                       if status == "failed"
                       else f"파일 생성 완료: {GENERATED_DIR / filename}")
            db.add(GenerateLog(
                file_type    = file_type,
                filename     = filename,
                status       = status,
                message      = message,
                triggered_by = triggered_by,
            ))
            results.append(result)

        db.commit()   # 루프 완료 후 한 번에 커밋
    finally:
        db.close()    # 예외가 발생해도 세션을 반드시 닫음

    return results
