"""
Bootstrap 정적 파일을 로컬에 다운로드하는 스크립트.
인터넷이 되는 PC에서 한 번 실행한 후 static/ 폴더를 VM 서버로 복사하세요.

사용법:
  python download_static.py
"""
import urllib.request
from pathlib import Path

BOOTSTRAP_VERSION = "5.3.3"
FILES = {
    f"https://cdn.jsdelivr.net/npm/bootstrap@{BOOTSTRAP_VERSION}/dist/css/bootstrap.min.css":
        "static/css/bootstrap.min.css",
    f"https://cdn.jsdelivr.net/npm/bootstrap@{BOOTSTRAP_VERSION}/dist/js/bootstrap.bundle.min.js":
        "static/js/bootstrap.bundle.min.js",
}

for url, dest in FILES.items():
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    print(f"다운로드 중: {url}")
    urllib.request.urlretrieve(url, dest)
    size = Path(dest).stat().st_size
    print(f"  저장 완료: {dest} ({size:,} bytes)")

print("\nBootstrap 파일 다운로드 완료!")
print("base.html의 CDN 링크를 로컬 경로로 변경하려면:")
print("  <link href='/static/css/bootstrap.min.css'>")
print("  <script src='/static/js/bootstrap.bundle.min.js'>")
