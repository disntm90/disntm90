"""
파일 생성 단독 테스트 스크립트.
웹 서버 없이 실행 가능. venv 활성화 후 실행:
  python test_generate.py
"""

import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

# -----------------------------------------------------------
# STEP 1: bigdataquery 임포트 확인
# -----------------------------------------------------------
print("=" * 50)
print("[1/3] bigdataquery 임포트 확인")
print("=" * 50)
try:
    import bigdataquery as bdq
    print("  OK: bigdataquery 임포트 성공\n")
except ImportError as e:
    print(f"  FAIL: {e}")
    print("  → pip install 로 bigdataquery를 먼저 설치하세요.")
    sys.exit(1)

# -----------------------------------------------------------
# STEP 2: DB 조회 확인
# -----------------------------------------------------------
print("=" * 50)
print("[2/3] DB 조회 확인")
print("=" * 50)
try:
    df = bdq.getData(param="""
        SELECT code_type, code_id
        FROM mos_tsp_smi.gpm_tp_be_mng_sbl_scrap_code
        WHERE vendor_name = 'ICOS'
    """)
    if df.empty:
        print("  WARN: 조회 성공했으나 데이터가 0건입니다.")
    else:
        print(f"  OK: {len(df)}건 조회 성공")
        print(f"  샘플 (상위 3건):\n{df.head(3).to_string(index=False)}\n")
except Exception as e:
    print(f"  FAIL: DB 조회 실패 → {e}")
    sys.exit(1)

# -----------------------------------------------------------
# STEP 3: X / Y 파일 생성
# -----------------------------------------------------------
print("=" * 50)
print("[3/3] 파일 생성")
print("=" * 50)

from app.database import init_db
init_db()

from app.services.file_generator import generate_yield_condef, generate_reject_mapfile
from config import GENERATED_DIR

results = []
for label, fn in [("X → YieldConvDef.xml", generate_yield_condef),
                  ("Y → RejectCodeMap.xml", generate_reject_mapfile)]:
    result = fn(triggered_by="test")
    status = result["status"]
    icon = "OK" if status == "success" else "FAIL"
    print(f"  {icon}: {label}")
    if status == "failed":
        print(f"       에러: {result.get('error')}")
    results.append(result)

# -----------------------------------------------------------
# 결과 요약
# -----------------------------------------------------------
print()
print("=" * 50)
print("결과 요약")
print("=" * 50)
all_ok = all(r["status"] == "success" for r in results)
if all_ok:
    print(f"  성공! 생성된 파일 위치: {GENERATED_DIR.resolve()}")
    for r in results:
        f = GENERATED_DIR / r["filename"]
        print(f"  - {r['filename']} ({f.stat().st_size:,} bytes)")
else:
    print("  일부 파일 생성 실패. 위 에러 메시지를 확인하세요.")
