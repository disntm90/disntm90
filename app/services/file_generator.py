"""
X, Y 파일 생성 서비스.

X파일: YieldConvDef.xml  - bigdataquery로 DB 조회 후 정렬하여 XML 생성
Y파일: RejectCodeMap.xml - bigdataquery + primecode.csv + static_xml_template.txt 조합
"""

import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from app.database import SessionLocal
from app.models import GenerateLog
from config import GENERATED_DIR, DATA_DIR

logger = logging.getLogger(__name__)

PRIMECODE_CSV = DATA_DIR / "primecode.csv"
TEMPLATE_FILE = DATA_DIR / "static_xml_template.txt"
DEFAULT_PRIMECODE = "9"

_BDQ_QUERY = """
    SELECT code_type, code_id
    FROM mos_tsp_smi.gpm_tp_be_mng_sbl_scrap_code
    WHERE vendor_name = 'ICOS'
"""

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


# ------------------------------------------------------------------
# 공통: DB 조회
# ------------------------------------------------------------------

def _fetch_scrap_data() -> Optional[pd.DataFrame]:
    try:
        import bigdataquery as bdq
    except ImportError:
        logger.error("bigdataquery 패키지가 설치되어 있지 않습니다.")
        return None

    try:
        df = bdq.getData(param=_BDQ_QUERY)
    except Exception as exc:
        logger.error(f"DB 조회 실패: {exc}")
        return None

    if df.empty:
        logger.warning("조회된 데이터가 없습니다.")
        return None

    return df.copy()


# ------------------------------------------------------------------
# X파일: YieldConvDef.xml
# ------------------------------------------------------------------

def generate_yield_condef(triggered_by: str = "scheduler") -> dict:
    filename = "YieldConvDef.xml"
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    df = _fetch_scrap_data()
    if df is None:
        return {"file_type": "X", "filename": filename, "status": "failed", "error": "DB 조회 실패 또는 데이터 없음"}

    conditions = [
        df["code_type"].str.startswith("BGA", na=False),
        df["code_type"].str.startswith("3D", na=False),
        df["code_type"].str.startswith("BBI", na=False),
        df["code_type"].str.startswith("TOPSMI", na=False),
    ]
    df["sort_priority"] = np.select(conditions, [1, 2, 3, 4], default=5)
    df.sort_values(by=["sort_priority", "code_id"], inplace=True)

    root = ET.Element("YieldDefinitions")
    yield_table = ET.SubElement(root, "YieldTable")
    title = ET.SubElement(yield_table, "Title")
    title.text = "Ranked Rejects"
    ranked_def = ET.SubElement(yield_table, "RankedYieldDefinition")
    for code_type in df["code_type"]:
        ET.SubElement(ranked_def, "Yield").text = str(code_type)

    ET.indent(root, space="  ")
    output_path = GENERATED_DIR / filename
    ET.ElementTree(root).write(str(output_path), encoding="utf-8", xml_declaration=True)

    logger.info(f"X파일 생성 완료: {output_path} ({len(df)}개 항목)")
    return {"file_type": "X", "filename": filename, "status": "success"}


# ------------------------------------------------------------------
# Y파일: RejectCodeMap.xml
# ------------------------------------------------------------------

def _load_primecode_map() -> dict:
    if not PRIMECODE_CSV.exists():
        logger.warning(f"primecode.csv 없음 → 기본값({DEFAULT_PRIMECODE}) 사용: {PRIMECODE_CSV}")
        return {}

    for encoding in ("cp949", "utf-8"):
        try:
            df = pd.read_csv(PRIMECODE_CSV, dtype=str, encoding=encoding)
            mapping = {str(k).upper(): v for k, v in zip(df["code_type"], df["primecode"])}
            logger.info(f"primecode 매핑 로드 완료 – {len(mapping)}건 ({encoding})")
            return mapping
        except UnicodeDecodeError:
            continue
        except Exception as exc:
            logger.error(f"primecode.csv 파싱 오류: {exc}")
            return {}

    logger.error("primecode.csv 인코딩 감지 실패 (cp949/utf-8 모두 실패)")
    return {}


def _ensure_template() -> str:
    if not TEMPLATE_FILE.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        TEMPLATE_FILE.write_text(STATIC_XML_TEMPLATE, encoding="utf-8")
        logger.info(f"템플릿 파일 생성: {TEMPLATE_FILE}")
    return TEMPLATE_FILE.read_text(encoding="utf-8")


def generate_reject_mapfile(triggered_by: str = "scheduler") -> dict:
    filename = "RejectCodeMap.xml"
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    prime_map = _load_primecode_map()
    df = _fetch_scrap_data()
    if df is None:
        return {"file_type": "Y", "filename": filename, "status": "failed", "error": "DB 조회 실패 또는 데이터 없음"}

    df["prime_code"] = df["code_type"].astype(str).str.upper().map(prime_map).fillna(DEFAULT_PRIMECODE)
    df.sort_values(by=["prime_code", "code_id"], inplace=True)

    scrap_map_lines = [
        f'\t\t<ScrapMap RejectCode="{row.code_type}" PrimeCode="{row.prime_code}" SecondaryCode="{row.code_id}"/>'
        for row in df.itertuples(index=False)
    ]
    dynamic_xml = "\n".join(scrap_map_lines)

    template = _ensure_template()
    final_xml = template.replace("{DYNAMIC_SCRAP_MAPS}", dynamic_xml)

    output_path = GENERATED_DIR / filename
    if output_path.exists():
        backup = output_path.with_suffix(".bak")
        try:
            os.replace(str(output_path), str(backup))
        except Exception as exc:
            logger.warning(f"백업 실패 (계속 진행): {exc}")

    output_path.write_text(final_xml, encoding="utf-8")
    logger.info(f"Y파일 생성 완료: {output_path} ({len(df)}개 항목)")
    return {"file_type": "Y", "filename": filename, "status": "success"}


# ------------------------------------------------------------------
# 외부 진입점 (스케줄러 / API에서 호출)
# ------------------------------------------------------------------

def generate_all_files(triggered_by: str = "scheduler") -> list[dict]:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    generators = [
        ("X", "YieldConvDef.xml", generate_yield_condef),
        ("Y", "RejectCodeMap.xml", generate_reject_mapfile),
    ]

    results = []
    db = SessionLocal()
    try:
        for file_type, filename, fn in generators:
            result = fn(triggered_by=triggered_by)
            status = result["status"]
            message = result.get("error", f"파일 생성 완료: {GENERATED_DIR / filename}") if status == "failed" else f"파일 생성 완료: {GENERATED_DIR / filename}"

            db.add(GenerateLog(
                file_type=file_type,
                filename=filename,
                status=status,
                message=message,
                triggered_by=triggered_by,
            ))
            results.append(result)

        db.commit()
    finally:
        db.close()

    return results
