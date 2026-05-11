"""
설비 배포 대시보드 실행 스크립트

사용법:
  python run.py              # 기본 (0.0.0.0:8000)
  python run.py --port 8080  # 포트 변경
"""
import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="개발 모드 (코드 변경 시 자동 재시작)")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
