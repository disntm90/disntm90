"""
run.py — 앱 실행 진입점

python run.py               # 모든 IP에서 8000 포트로 서비스
python run.py --port 8080   # 포트 변경
python run.py --reload      # 개발 모드 (코드 저장 시 자동 재시작)
"""
import argparse
import uvicorn  # FastAPI를 실행하는 ASGI 서버

if __name__ == "__main__":
    # 커맨드라인 인자 파서 설정
    parser = argparse.ArgumentParser(description="설비 배포 대시보드 실행")
    parser.add_argument("--host", default="0.0.0.0",
                        help="바인딩 호스트 (0.0.0.0 = 모든 네트워크 인터페이스)")
    parser.add_argument("--port", type=int, default=8000,
                        help="바인딩 포트 번호 (기본 8000)")
    parser.add_argument("--reload", action="store_true",
                        help="개발 모드: 코드 변경 시 자동 재시작 (운영 환경에서 사용 금지)")
    args = parser.parse_args()

    # uvicorn으로 FastAPI 앱 실행
    # "app.main:app" → app/main.py 안의 app 객체를 가리킴
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
