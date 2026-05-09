from fastapi import FastAPI
from routes import router

# ────────────────────────────────────────────
# FastAPI 앱 초기화
# ────────────────────────────────────────────
app = FastAPI(
    title="UX-Swarm API",
    description="AI 페르소나 UX 시뮬레이션 API",
    version="1.0.0",
)

# 라우터 등록
app.include_router(router)


# ────────────────────────────────────────────
# 헬스체크
# EC2 로드밸런서 또는 Spring이 서버 살아있는지 확인용
# ────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "ok"}