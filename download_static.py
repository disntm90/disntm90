"""
Bootstrap / HTMX 정적 파일을 로컬에 다운로드하는 스크립트.
인터넷이 되는 PC에서 한 번 실행한 후 static/ 폴더를 VM 서버로 복사하세요.

사용법:
  python download_static.py

다운로드 순서 (자동 폴백):
  1순위: Windows 내장 curl.exe  (Windows 10 1803 / Server 2019 이상)
  2순위: PowerShell Invoke-WebRequest
  3순위: Python urllib (SSL 검증 우회 포함)
"""
import subprocess
import sys
import ssl
import urllib.request
from pathlib import Path

BOOTSTRAP_VERSION = "5.3.3"
HTMX_VERSION      = "1.9.12"

FILES = [
    (
        f"https://cdn.jsdelivr.net/npm/bootstrap@{BOOTSTRAP_VERSION}/dist/css/bootstrap.min.css",
        "static/css/bootstrap.min.css",
    ),
    (
        f"https://cdn.jsdelivr.net/npm/bootstrap@{BOOTSTRAP_VERSION}/dist/js/bootstrap.bundle.min.js",
        "static/js/bootstrap.bundle.min.js",
    ),
    (
        f"https://cdn.jsdelivr.net/npm/htmx.org@{HTMX_VERSION}/dist/htmx.min.js",
        "static/js/htmx.min.js",
    ),
]


def _try_curl(url: str, dest: str) -> bool:
    """Windows 내장 curl.exe로 다운로드 (Windows 10 1803+ / Server 2019+)."""
    try:
        result = subprocess.run(
            ["curl.exe", "-L", "--ssl-no-revoke", "-o", dest, url],
            capture_output=True, timeout=60,
        )
        if result.returncode == 0 and Path(dest).exists():
            return True
        # curl 오류 메시지 표시
        print(f"    curl 오류: {result.stderr.decode(errors='replace').strip()}")
    except FileNotFoundError:
        pass  # curl.exe 없으면 다음 방법으로
    except Exception as e:
        print(f"    curl 예외: {e}")
    return False


def _try_powershell(url: str, dest: str) -> bool:
    """PowerShell Invoke-WebRequest로 다운로드 (Windows 내장, WinHTTP 사용)."""
    dest_abs = str(Path(dest).resolve())
    ps_cmd = (
        f"[Net.ServicePointManager]::SecurityProtocol = "
        f"[Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13; "
        f"Invoke-WebRequest -Uri '{url}' -OutFile '{dest_abs}' -UseBasicParsing"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, timeout=60,
        )
        if result.returncode == 0 and Path(dest).exists():
            return True
        print(f"    PowerShell 오류: {result.stderr.decode(errors='replace').strip()}")
    except Exception as e:
        print(f"    PowerShell 예외: {e}")
    return False


def _try_urllib(url: str, dest: str) -> bool:
    """Python urllib으로 다운로드 (SSL 검증 우회 포함)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            Path(dest).write_bytes(resp.read())
        return Path(dest).exists()
    except Exception as e:
        print(f"    urllib 오류: {e}")
    return False


def download(url: str, dest: str) -> None:
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    print(f"다운로드 중: {url}")

    methods = [
        ("curl.exe",    _try_curl),
        ("PowerShell",  _try_powershell),
        ("urllib",      _try_urllib),
    ]

    for name, fn in methods:
        print(f"  [{name}] 시도 중...", end=" ", flush=True)
        if fn(url, dest):
            size = Path(dest).stat().st_size
            print(f"완료 ({size:,} bytes)")
            return
        print("실패")

    # 세 가지 방법 모두 실패
    print()
    print("=" * 60)
    print(f"[수동 다운로드 필요]")
    print(f"  URL  : {url}")
    print(f"  저장 : {dest}")
    print("  브라우저에서 위 URL에 접속해 직접 저장하세요.")
    print("=" * 60)
    sys.exit(1)


for url, dest in FILES:
    download(url, dest)

print("\n정적 파일 다운로드 완료!")
print("static/ 폴더를 VM 서버의 프로젝트 루트에 복사하세요.")
