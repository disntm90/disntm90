"""
Bootstrap / HTMX 정적 파일을 로컬에 다운로드하는 스크립트.
인터넷이 되는 PC에서 한 번 실행한 후 static/ 폴더를 VM 서버로 복사하세요.

사용법:
  python download_static.py

문제 해결:
  - [WinError 10054] ConnectionResetError  → User-Agent 헤더 + TLS 설정으로 해결
  - 프록시 환경                            → 환경변수 HTTPS_PROXY=http://proxy:port 설정 후 실행
"""
import ssl
import time
import urllib.request
from pathlib import Path

BOOTSTRAP_VERSION = "5.3.3"
HTMX_VERSION      = "1.9.12"

FILES = {
    f"https://cdn.jsdelivr.net/npm/bootstrap@{BOOTSTRAP_VERSION}/dist/css/bootstrap.min.css":
        "static/css/bootstrap.min.css",
    f"https://cdn.jsdelivr.net/npm/bootstrap@{BOOTSTRAP_VERSION}/dist/js/bootstrap.bundle.min.js":
        "static/js/bootstrap.bundle.min.js",
    f"https://cdn.jsdelivr.net/npm/htmx.org@{HTMX_VERSION}/dist/htmx.min.js":
        "static/js/htmx.min.js",
}

# CDN이 Python urllib의 기본 User-Agent를 차단하는 경우가 있어 브라우저로 위장
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

# SSL 인증서 검증 실패 시 우회 컨텍스트 (사내 프록시가 인증서를 교체하는 환경 대응)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode    = ssl.CERT_NONE


def download(url: str, dest: str, retries: int = 3) -> None:
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    print(f"다운로드 중: {url}")

    req = urllib.request.Request(url, headers=HEADERS)
    last_err = None

    for attempt in range(1, retries + 1):
        try:
            # 먼저 정상 SSL 검증으로 시도
            with urllib.request.urlopen(req, timeout=30) as resp:
                Path(dest).write_bytes(resp.read())
            size = Path(dest).stat().st_size
            print(f"  저장 완료: {dest} ({size:,} bytes)")
            return
        except Exception as e:
            last_err = e
            if attempt == 1:
                # 두 번째 시도부터 SSL 검증 우회 (사내 프록시 대응)
                try:
                    with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
                        Path(dest).write_bytes(resp.read())
                    size = Path(dest).stat().st_size
                    print(f"  저장 완료 (SSL 우회): {dest} ({size:,} bytes)")
                    return
                except Exception as e2:
                    last_err = e2
            print(f"  재시도 {attempt}/{retries}: {e}")
            time.sleep(2 ** attempt)  # 2s, 4s 대기 후 재시도

    raise RuntimeError(f"다운로드 실패 ({url}): {last_err}")


for url, dest in FILES.items():
    download(url, dest)

print("\n정적 파일 다운로드 완료!")
print("static/ 폴더를 VM 서버의 프로젝트 루트에 복사하세요.")
