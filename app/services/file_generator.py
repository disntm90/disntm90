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
DEFAULT_PRIMECODE = "9"   # primecode.csv에 없는 code_type에 적용할 기본값

# ── 배포 대상 파일 목록 (단일 소스) ──────────────────────────────
# (파일타입, 파일명, 설비 내 배포 경로)
# deployer.py가 이 목록을 import해서 사용하므로, 경로 변경 시 여기만 수정한다.
OUTPUT_FILES = [
    ("YieldConvDef",  "YieldConvDef.xml",  "C:/Icos"),
    ("RejectMapFile", "RejectMapFile.xml",  "C:/Handler/SamsungAutomation/Configuration"),
]

# ── bigdataquery SQL ──────────────────────────────────────────────
# ICOS 벤더 기준의 불량 코드 목록 조회
_BDQ_QUERY = """
    SELECT code_type, code_id
    FROM mos_tsp_smi.gpm_tp_be_mng_sbl_scrap_code
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
        <ScrapCode Name="역 M/K" ID="10"/>
        <ScrapCode Name="M/K 안됨" ID="11"/>
        <ScrapCode Name="이중 M/K" ID="12"/>
        <ScrapCode Name="M/K 끊김" ID="13"/>
        <ScrapCode Name="M/K 위치" ID="14"/>
        <ScrapCode Name="M/K 각도" ID="15"/>
        <ScrapCode Name="M/K OCR" ID="16"/>
        <ScrapCode Name="PIN 1" ID="17"/>
        <ScrapCode Name="DATE CODE 인식불량" ID="18"/>
        <ScrapCode Name="PKG 소지금속노출" ID="20"/>
        <ScrapCode Name="PKG 긁힘" ID="21"/>
        <ScrapCode Name="PKG 기공" ID="22"/>
        <ScrapCode Name="PKG 금감" ID="23"/>
        <ScrapCode Name="PKG 깨짐" ID="24"/>
        <ScrapCode Name="PKG 오염" ID="25"/>
        <ScrapCode Name="PKG Size" ID="26"/>
        <ScrapCode Name="PKG Offset" ID="27"/>
        <ScrapCode Name="Ball Cop" ID="30"/>
        <ScrapCode Name="Ball Quality" ID="31"/>
        <ScrapCode Name="Ball Pitch" ID="32"/>
        <ScrapCode Name="Ball Width" ID="33"/>
        <ScrapCode Name="Ball Offset" ID="34"/>
        <ScrapCode Name="Ball Count" ID="35"/>
        <ScrapCode Name="Ball 이물질" ID="36"/>
        <ScrapCode Name="Non Wet" ID="37"/>
        <ScrapCode Name="PCB 소지금속노출" ID="40"/>
        <ScrapCode Name="PCB Scratch" ID="41"/>
        <ScrapCode Name="PCB Open" ID="42"/>
        <ScrapCode Name="PCB/PSR Crack" ID="43"/>
        <ScrapCode Name="PCB 깨짐" ID="44"/>
        <ScrapCode Name="PCB 실오라기" ID="45"/>
        <ScrapCode Name="PCB 이물질" ID="46"/>
        <ScrapCode Name="Window Mold 소지금속노출" ID="47"/>
        <ScrapCode Name="Ball Index" ID="48"/>
        <ScrapCode Name="Encap Height" ID="50"/>
        <ScrapCode Name="Encap Overflow" ID="51"/>
        <ScrapCode Name="Encap Crack" ID="52"/>
        <ScrapCode Name="Encap Void" ID="53"/>
        <ScrapCode Name="Encap 박리" ID="54"/>
        <ScrapCode Name="Missing Ball" ID="55"/>
        <ScrapCode Name="Encap 이물질" ID="56"/>
        <ScrapCode Name="Chip Out" ID="57"/>
        <ScrapCode Name="Chip Crack" ID="58"/>
        <ScrapCode Name="Wire Reject" ID="59"/>
        <ScrapCode Name="Lead Cop" ID="60"/>
        <ScrapCode Name="Lead Pitch" ID="61"/>
        <ScrapCode Name="Lead Tin Burr" ID="62"/>
        <ScrapCode Name="Lead TD/LD" ID="63"/>
        <ScrapCode Name="Lead Span/Spread/Skew" ID="64"/>
        <ScrapCode Name="Lead Misalign" ID="65"/>
        <ScrapCode Name="No Solder" ID="66"/>
        <ScrapCode Name="Lead 변색" ID="67"/>
        <ScrapCode Name="Solder 고드름" ID="68"/>
        <ScrapCode Name="Lead/Ball Cop" ID="70"/>
        <ScrapCode Name="Lead Pitch" ID="71"/>
        <ScrapCode Name="Lead Tin Burr/Ball Quality" ID="72"/>
        <ScrapCode Name="Lead TD/LD" ID="73"/>
        <ScrapCode Name="Lead Span/Spread/Skew" ID="74"/>
        <ScrapCode Name="Lead Misalign" ID="75"/>
        <ScrapCode Name="No Solder" ID="76"/>
        <ScrapCode Name="Lead 변색" ID="77"/>
        <ScrapCode Name="Solder 고드름" ID="78"/>
        <ScrapCode Name="PCB Fail" ID="79"/>
        <ScrapCode Name="역 M/K" ID="80"/>
        <ScrapCode Name="M/K 안됨" ID="81"/>
        <ScrapCode Name="이중 M/K" ID="82"/>
        <ScrapCode Name="M/K 끊김" ID="83"/>
        <ScrapCode Name="M/K 위치" ID="84"/>
        <ScrapCode Name="M/K 각도" ID="85"/>
        <ScrapCode Name="M/K OCR" ID="86"/>
        <ScrapCode Name="PIN 1" ID="87"/>
        <ScrapCode Name="PCB Fail" ID="88"/>
        <ScrapCode Name="Invalid" ID="90"/>
        <ScrapCode Name="수량차이" ID="91"/>
        <ScrapCode Name="Double DVC" ID="92"/>
        <ScrapCode Name="제품 MIX" ID="93"/>
        <ScrapCode Name="Bin MIX" ID="94"/>
        <ScrapCode Name="Version MIX" ID="95"/>
        <ScrapCode Name="Line MIX" ID="96"/>
        <ScrapCode Name="Lot MIX" ID="97"/>
        <ScrapCode Name="WeeK MIX" ID="98"/>
        <ScrapCode Name="공손" ID="99"/>
        <ScrapCode Name="LICC 깨짐" ID="126"/>
        <ScrapCode Name="2D MK 불량 (PMS)" ID="0189"/>
        <ScrapCode Name="2차 Reject Total" ID="200"/>
        <ScrapCode Name="재현성시험시료" ID="270"/>
        <ScrapCode Name="MBT-BIN2" ID="520"/>
        <ScrapCode Name="BIN DOWN" ID="521"/>
        <ScrapCode Name="MBT-BIN3" ID="530"/>
        <ScrapCode Name="BIN DOWN" ID="531"/>
        <ScrapCode Name="MBT-BIN4" ID="540"/>
        <ScrapCode Name="Final-Bin5" ID="550"/>
        <ScrapCode Name="Final-Bin6" ID="560"/>
        <ScrapCode Name="Final-Bin7" ID="570"/>
        <ScrapCode Name="Final-Bin8" ID="580"/>
        <ScrapCode Name="실물 있는 경우" ID="590"/>
        <ScrapCode Name="공정성 BURNT" ID="591"/>
        <ScrapCode Name="제품성 BURNT" ID="592"/>
        <ScrapCode Name="B/I Contact Fail" ID="593"/>
        <ScrapCode Name="CHIP CARRIER 분리" ID="594"/>
        <ScrapCode Name="실물 없는 경우" ID="596"/>
        <ScrapCode Name="ASSY WARPAGE" ID="700"/>
        <ScrapCode Name="M-RUN 2차 FAIL" ID="1000"/>
        <ScrapCode Name="QA AQL REJECT" ID="2000"/>
        <ScrapCode Name="실물/전산불일치" ID="3000"/>
        <ScrapCode Name="LABEL 짤림" ID="3001"/>
        <ScrapCode Name="L/B OPTION 오류" ID="3002"/>
        <ScrapCode Name="설비 LEAD OFF" ID="3003"/>
        <ScrapCode Name="설비 M/K OFF" ID="3004"/>
        <ScrapCode Name="낙석DVC" ID="3005"/>
        <ScrapCode Name="ACCEPT미날인" ID="3006"/>
        <ScrapCode Name="LABEL 바뀜" ID="3007"/>
        <ScrapCode Name="DOUBLE DEVICE" ID="3008"/>
        <ScrapCode Name="IC역투입" ID="3009"/>
        <ScrapCode Name="LABEL미발행" ID="3010"/>
        <ScrapCode Name="JOB지정불량" ID="3011"/>
        <ScrapCode Name="LOT TYPE전환" ID="3012"/>
        <ScrapCode Name="AQLPRT미의뢰" ID="3013"/>
        <ScrapCode Name="AQLPRT오류" ID="3014"/>
        <ScrapCode Name="TRAY MIX" ID="3015"/>
        <ScrapCode Name="TRAY 역방향" ID="3016"/>
        <ScrapCode Name="빈POCKET" ID="3017"/>
        <ScrapCode Name="전산미처리" ID="3018"/>
        <ScrapCode Name="INDEX짤림" ID="3019"/>
        <ScrapCode Name="LABEL오류" ID="3020"/>
        <ScrapCode Name="수율저하" ID="3021"/>
        <ScrapCode Name="C/T HOLE찍힘" ID="3022"/>
        <ScrapCode Name="C/T 찢어짐" ID="3023"/>
        <ScrapCode Name="SEALING끊김" ID="3024"/>
        <ScrapCode Name="COB CRACK" ID="3025"/>
        <ScrapCode Name="LEAD짤림" ID="3026"/>
        <ScrapCode Name="PCB긁힘" ID="3027"/>
        <ScrapCode Name="PCB 오염" ID="3028"/>
        <ScrapCode Name="SIMAX LOSS 복원용" ID="3999"/>
        <ScrapCode Name="QUAL 의뢰용(기흥)" ID="5000"/>
        <ScrapCode Name="제조운영요청SCRAP" ID="7192"/>
        <ScrapCode Name="Front 공정에 기인한 불량 Scrap" ID="8100"/>
        <ScrapCode Name="Mold 공정에 기인한 불량 Scrap" ID="8200"/>
        <ScrapCode Name="Finish 공정에 기인한 불량 Scrap" ID="8300"/>
        <ScrapCode Name="원부자재에 기인한 불량 Scrap" ID="8400"/>
        <ScrapCode Name="FAB성 부적합제품(특성불량)" ID="9000"/>
        <ScrapCode Name="(L/F원자재) 소지금속노출" ID="9100"/>
        <ScrapCode Name="A/V REFORM 후 SCRAP 물량" ID="9200"/>
        <ScrapCode Name="판매불용 제품" ID="9500"/>
        <ScrapCode Name="PKG Qual(Eval)의뢰 제품" ID="9501"/>
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
    복원은 sys.__stdin__ (Python 시작 시 원본 stdin)을 사용한다.
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
        sys.stdin = sys.__stdin__  # 원본 stdin으로 복원 (캡처 값 아닌 Python 시작 시 원본)


def _fetch_scrap_data() -> Optional[pd.DataFrame]:
    """
    DB에서 불량 코드 목록을 조회한다.

    호출될 때마다 bdq.getData()를 새로 실행해 상위 서버의 최신 데이터를 반영한다.
    데이터를 캐싱하지 않으며, 로그인은 앱 시작 시 완료된 세션을 재사용한다.
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

    logger.info(f"getData 호출: user_name='{user}'")
    try:
        df = bdq.getData(param=_BDQ_QUERY, user_name=user)
    except Exception as exc:
        logger.error(f"DB 조회 실패: {exc}")
        return None

    if df.empty:
        logger.warning("조회된 데이터가 없습니다.")
        return None

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
        ET.SubElement(ranked_def, "Yield").text = str(code_type)

    ET.indent(root, space="  ")    # 들여쓰기 적용 (가독성)
    output_path = GENERATED_DIR / filename
    ET.ElementTree(root).write(str(output_path), encoding="utf-8", xml_declaration=True)

    # ── 무결성 검증 ───────────────────────────────────────────────
    valid, validation_msg = _validate_xml(output_path, expected_root="YieldDefinitions", min_items=3)
    if not valid:
        logger.error(f"YieldConvDef 무결성 검증 실패: {validation_msg}")
        return {"file_type": "YieldConvDef", "filename": filename,
                "status": "failed", "error": validation_msg}

    logger.info(f"YieldConvDef 생성 완료: {output_path} ({len(df)}개 항목, {validation_msg})")
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


def _load_template_content() -> str:
    """
    DB FileTemplate 테이블에서 RejectMapFile 템플릿을 읽는다.
    행이 없거나 내용이 비어 있으면 STATIC_XML_TEMPLATE 상수로 폴백한다.
    """
    from app.models import FileTemplate

    db = SessionLocal()
    try:
        t = db.query(FileTemplate).filter(
            FileTemplate.file_type == "RejectMapFile",
            FileTemplate.is_active == True,
        ).first()
        if t and t.content.strip():
            logger.info("DB에서 RejectMapFile 템플릿 로드")
            return t.content
    except Exception as exc:
        logger.error(f"DB 템플릿 조회 실패, 상수 폴백: {exc}")
    finally:
        db.close()

    logger.warning("DB에 RejectMapFile 템플릿 없음 → STATIC_XML_TEMPLATE 사용")
    return STATIC_XML_TEMPLATE


def generate_reject_mapfile(triggered_by: str = "scheduler") -> dict:
    """
    RejectMapFile.xml 을 생성한다.

    호출될 때마다 DB를 새로 조회해 최신 데이터를 반영한다.
    생성 과정:
      1. primecode.csv 로 code_type → prime_code 매핑 로드
      2. DB 데이터에 prime_code 컬럼 추가
      3. prime_code, code_id 순 정렬
      4. 각 행을 <ScrapMap .../> 태그로 변환
      5. 정적 템플릿의 {DYNAMIC_SCRAP_MAPS} 위치에 삽입
      6. XML 무결성 검증
    """
    filename = "RejectMapFile.xml"
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    prime_map = _load_primecode_map()

    df = _fetch_scrap_data()
    if df is None:
        return {"file_type": "RejectMapFile", "filename": filename,
                "status": "failed", "error": "DB 조회 실패 또는 데이터 없음"}

    df = df.copy()

    # code_type을 대문자로 변환 후 prime_map에서 값 조회
    # 매핑이 없는 항목은 DEFAULT_PRIMECODE("9")로 채움
    df["prime_code"] = df["code_type"].astype(str).str.upper().map(prime_map).fillna(DEFAULT_PRIMECODE)
    df.sort_values(by=["prime_code", "code_id"], inplace=True)

    # 각 행을 XML 태그 한 줄로 변환
    scrap_map_lines = [
        f'\t\t<ScrapMap RejectCode="{row.code_type}" PrimeCode="{row.prime_code}" SecondaryCode="{row.code_id}"/>'
        for row in df.itertuples(index=False)
    ]
    dynamic_xml = "\n".join(scrap_map_lines)   # 여러 줄을 개행으로 합침

    # 정적 템플릿에 동적 부분 삽입
    template  = _load_template_content()
    final_xml = template.replace("{DYNAMIC_SCRAP_MAPS}", dynamic_xml)

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

    logger.info(f"RejectMapFile 생성 완료: {output_path} ({len(df)}개 항목, {validation_msg})")
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
