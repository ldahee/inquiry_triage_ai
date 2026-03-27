"""
FastAPI 문의 처리 API 엔드포인트.
API 레이어에서는 LangGraph 실행을 직접 구현하지 않고 서비스 레이어만 호출합니다.
"""
import hmac
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.services.inquiry_service import InquiryService

KST = timezone(timedelta(hours=9))
# { key: (count, "YYYY-MM-DD") }
_daily_counts: dict[str, tuple[int, str]] = {}

router = APIRouter(prefix="/api/v1/inquiries", tags=["inquiries"])

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_OPERATOR_KEY_HEADER = APIKeyHeader(name="X-Operator-Key", auto_error=False)


class InquiryRequest(BaseModel):
    inquiry_text: str = Field(..., min_length=1, max_length=2000, description="고객 문의 텍스트")
    user_id: Optional[str] = Field(default=None, description="사용자 ID (선택)")
    channel: Optional[str] = Field(default=None, description="문의 채널 (선택)")
    locale: Optional[str] = Field(default=None, description="로케일 (선택)")
    mode: Literal["user", "operator"] = Field(
        default="user",
        description="응답 모드. user=최종 답변만, operator=전체 처리 메타데이터 포함",
    )
    conversation_id: Optional[str] = Field(default=None, description="대화 ID (멀티턴용, user 모드 전용)")


class ExecutionTraceItem(BaseModel):
    node_name: str
    status: str
    duration_ms: Optional[int] = None


class UserResponse(BaseModel):
    answer: str
    conversation_id: str


class OperatorResponse(BaseModel):
    category: Optional[str]
    confidence: Optional[float]
    selected_agent: Optional[str]
    answer: Optional[str]
    fallback_used: bool
    routing_reason: Optional[str]
    execution_trace: list[dict]
    latency_ms: int


class InquiryErrorDetail(BaseModel):
    code: str
    message: str


class InquiryErrorResponse(BaseModel):
    error: InquiryErrorDetail


def _check_daily_limit(key: str) -> None:
    today = datetime.now(KST).strftime("%Y-%m-%d")
    count, date = _daily_counts.get(key, (0, today))
    if date != today:
        count = 0
    if count >= settings.daily_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"오늘 사용 가능한 횟수({settings.daily_limit}회)를 모두 소진했습니다. 내일 자정 이후 다시 이용해 주세요.",
            },
        )
    _daily_counts[key] = (count + 1, today)


@router.post(
    "/respond",
    status_code=status.HTTP_200_OK,
    summary="고객 문의 분류 및 답변 생성",
)
async def respond_to_inquiry(
    request: Request,
    body: InquiryRequest,
    api_key: str = Security(_API_KEY_HEADER),
    operator_key: str = Security(_OPERATOR_KEY_HEADER),
) -> dict:
    # 일반 API 키 검증
    if settings.api_key and not hmac.compare_digest(api_key or "", settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "유효하지 않은 API 키입니다."},
        )

    # 운영자 모드 접근 검증
    if body.mode == "operator":
        if settings.operator_api_key and not hmac.compare_digest(operator_key or "", settings.operator_api_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "운영자 접근 권한이 없습니다."},
            )

    # 일별 사용량 제한
    limit_key = body.user_id or request.client.host
    _check_daily_limit(limit_key)

    service = InquiryService()
    result = await service.process_inquiry(
        inquiry_text=body.inquiry_text,
        user_id=body.user_id,
        channel=body.channel,
        locale=body.locale,
        conversation_id=body.conversation_id if body.mode == "user" else None,
    )

    if "error" in result:
        error = result["error"]
        code = error.get("code", "INTERNAL_ERROR")
        http_status = _error_code_to_http_status(code)

        # user 모드에서는 500 에러의 내부 코드를 노출하지 않음
        if body.mode == "user" and http_status == 500:
            raise HTTPException(
                status_code=http_status,
                detail={"code": "INTERNAL_ERROR", "message": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."},
            )
        raise HTTPException(
            status_code=http_status,
            detail={"code": code, "message": error.get("message")},
        )

    if body.mode == "user":
        return {"answer": result.get("answer"), "conversation_id": result.get("conversation_id")}

    # operator mode: 전체 메타데이터 반환
    return {
        "category": result.get("category"),
        "confidence": result.get("confidence"),
        "selected_agent": result.get("selected_agent"),
        "answer": result.get("answer"),
        "fallback_used": result.get("fallback_used", False),
        "routing_reason": result.get("routing_reason"),
        "execution_trace": result.get("execution_trace", []),
        "latency_ms": result.get("latency_ms", 0),
    }


def _error_code_to_http_status(code: str) -> int:
    return {
        "INVALID_INPUT": status.HTTP_400_BAD_REQUEST,
        "SAFETY_BLOCKED": status.HTTP_400_BAD_REQUEST,
        "ROUTING_FAILED": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "AGENT_EXECUTION_FAILED": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "OUTPUT_PARSE_FAILED": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }.get(code, status.HTTP_500_INTERNAL_SERVER_ERROR)
