"""
문의 처리 서비스 레이어.
LangGraph 실행 및 응답 반환을 담당합니다.
"""
import logging
import time
import uuid
from typing import Optional

from app.config.database import is_db_enabled, _session_factory
from app.graphs.inquiry_graph import inquiry_graph
from app.repositories.inquiry_repository import ConversationRepository, InquiryRepository
from app.schemas.inquiry_state import InquiryState

logger = logging.getLogger(__name__)


class InquiryService:
    async def process_inquiry(
        self,
        inquiry_text: str,
        user_id: Optional[str] = None,
        channel: Optional[str] = None,
        locale: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """
        문의를 처리하고 최종 응답을 반환합니다.
        """
        start_time = time.monotonic()

        conversation_id = conversation_id or str(uuid.uuid4())
        chat_history = await self._load_chat_history(conversation_id)

        initial_state: InquiryState = {
            "inquiry_text": inquiry_text,
            "user_id": user_id,
            "channel": channel,
            "locale": locale,
            "inquiry_id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "chat_history": chat_history,
            "category": None,
            "confidence": None,
            "routing_reason": None,
            "selected_agent": None,
            "answer": None,
            "safety_flag": None,
            "fallback_used": False,
            "retry_count": 0,
            "llm_call_count": 0,
            "error": None,
            "execution_trace": [],
        }

        try:
            final_state: InquiryState = await inquiry_graph.ainvoke(initial_state)
        except Exception as e:
            logger.exception("inquiry_graph execution failed: %s", e)
            return {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "문의 분류 또는 답변 생성에 실패했습니다.",
                }
            }

        latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "[%s] process_inquiry completed in %dms | category=%s confidence=%.2f agent=%s fallback=%s",
            final_state.get("inquiry_id"),
            latency_ms,
            final_state.get("category"),
            final_state.get("confidence") or 0.0,
            final_state.get("selected_agent"),
            final_state.get("fallback_used"),
        )

        # 에러 응답
        if final_state.get("error") and not final_state.get("answer"):
            return {
                "error": {
                    "code": final_state["error"],
                    "message": "문의 분류 또는 답변 생성에 실패했습니다.",
                }
            }

        answer = final_state.get("answer")
        result = {
            "category": final_state.get("category"),
            "confidence": final_state.get("confidence"),
            "selected_agent": final_state.get("selected_agent"),
            "answer": answer,
            "fallback_used": final_state.get("fallback_used", False),
            "routing_reason": final_state.get("routing_reason"),
            "execution_trace": final_state.get("execution_trace", []),
            "latency_ms": latency_ms,
            "conversation_id": conversation_id,
        }

        if answer:
            await self._save_conversation_messages(conversation_id, inquiry_text, answer)

        await self._save_to_db(
            inquiry_text=inquiry_text,
            user_id=user_id,
            channel=channel,
            locale=locale,
            state=final_state,
            latency_ms=latency_ms,
        )

        return result

    async def _load_chat_history(self, conversation_id: str) -> list:
        if not is_db_enabled():
            return []
        try:
            async with _session_factory() as session:
                repo = ConversationRepository(session)
                return await repo.get_messages(conversation_id)
        except Exception as e:
            logger.error("대화 이력 로드 실패 (빈 이력으로 진행): %s", e)
            return []

    async def _save_conversation_messages(
        self, conversation_id: str, inquiry_text: str, answer: str
    ) -> None:
        if not is_db_enabled():
            return
        try:
            async with _session_factory() as session:
                repo = ConversationRepository(session)
                await repo.append_messages(conversation_id, inquiry_text, answer)
        except Exception as e:
            logger.error("대화 메시지 저장 실패 (응답에는 영향 없음): %s", e)

    async def _save_to_db(
        self,
        inquiry_text: str,
        user_id: Optional[str],
        channel: Optional[str],
        locale: Optional[str],
        state: InquiryState,
        latency_ms: int,
    ) -> None:
        if not is_db_enabled():
            return
        try:
            async with _session_factory() as session:
                repo = InquiryRepository(session)
                await repo.save(
                    inquiry_id=state["inquiry_id"],
                    inquiry_text=inquiry_text,
                    user_id=user_id,
                    channel=channel,
                    locale=locale,
                    category=state.get("category"),
                    confidence=state.get("confidence"),
                    routing_reason=state.get("routing_reason"),
                    selected_agent=state.get("selected_agent"),
                    answer=state.get("answer"),
                    safety_flag=state.get("safety_flag"),
                    fallback_used=state.get("fallback_used", False),
                    retry_count=state.get("retry_count", 0),
                    llm_call_count=state.get("llm_call_count", 0),
                    latency_ms=latency_ms,
                    error=state.get("error"),
                    execution_trace=state.get("execution_trace", []),
                )
        except Exception as e:
            logger.error("[%s] DB 저장 실패 (응답에는 영향 없음): %s", state.get("inquiry_id"), e)

