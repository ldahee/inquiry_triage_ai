import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.inquiry_router import router as inquiry_router
from app.config.limiter import limiter
from app.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="고객 문의 자동응답 시스템",
    description="LangChain + LangGraph 기반 멀티 에이전트 문의 분류 및 답변 생성 시스템",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inquiry_router)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
