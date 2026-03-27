"""
문의 이력 저장 레포지토리.
개인정보(전화번호, 이메일, 카드번호, 주민등록번호) 마스킹 후 저장합니다.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import Base

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 모델
# ──────────────────────────────────────────────

class InquiryLog(Base):
    __tablename__ = "inquiry_logs"

    inquiry_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    channel: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    locale: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    inquiry_text_masked: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    routing_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selected_agent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    safety_flag: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    execution_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # "human" | "ai"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


# ──────────────────────────────────────────────
# PII 마스킹
# ──────────────────────────────────────────────

_PHONE_RE = re.compile(r"\d{2,3}-\d{3,4}-\d{4}|\d{10,11}")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_CARD_RE = re.compile(r"\d{4}-\d{4}-\d{4}-\d{4}|\d{16}")
_RRN_RE = re.compile(r"\d{6}-\d{7}")


def mask_pii(text: str) -> str:
    text = _RRN_RE.sub("[RRN]", text)
    text = _CARD_RE.sub("[CARD]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _EMAIL_RE.sub("[EMAIL]", text)
    return text


# ──────────────────────────────────────────────
# 레포지토리
# ──────────────────────────────────────────────

class InquiryRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(
        self,
        inquiry_id: str,
        inquiry_text: str,
        user_id: Optional[str],
        channel: Optional[str],
        locale: Optional[str],
        category: Optional[str],
        confidence: Optional[float],
        routing_reason: Optional[str],
        selected_agent: Optional[str],
        answer: Optional[str],
        safety_flag: Optional[bool],
        fallback_used: bool,
        retry_count: int,
        llm_call_count: int,
        latency_ms: Optional[int],
        error: Optional[str],
        execution_trace: list,
    ) -> None:
        log = InquiryLog(
            inquiry_id=inquiry_id,
            user_id=user_id,
            channel=channel,
            locale=locale,
            inquiry_text_masked=mask_pii(inquiry_text),
            category=category,
            confidence=confidence,
            routing_reason=routing_reason,
            selected_agent=selected_agent,
            answer=answer,
            safety_flag=safety_flag,
            fallback_used=fallback_used,
            retry_count=retry_count,
            llm_call_count=llm_call_count,
            latency_ms=latency_ms,
            error=error,
            execution_trace=json.dumps(execution_trace, ensure_ascii=False),
        )
        self._session.add(log)
        await self._session.commit()


# ──────────────────────────────────────────────
# 대화 레포지토리
# ──────────────────────────────────────────────

MAX_HISTORY_MESSAGES = 20  # 최근 10턴 (human + ai)


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_messages(self, conversation_id: str) -> list:
        """대화 이력을 BaseMessage 리스트로 반환합니다."""
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(MAX_HISTORY_MESSAGES)
        )
        result = await self._session.execute(stmt)
        rows = list(reversed(result.scalars().all()))

        messages = []
        for row in rows:
            if row.role == "human":
                messages.append(HumanMessage(content=row.content))
            else:
                messages.append(AIMessage(content=row.content))
        return messages

    async def append_messages(
        self, conversation_id: str, human_text: str, ai_text: str
    ) -> None:
        """human + ai 메시지 쌍을 저장합니다."""
        self._session.add(ConversationMessage(
            conversation_id=conversation_id,
            role="human",
            content=mask_pii(human_text),
        ))
        self._session.add(ConversationMessage(
            conversation_id=conversation_id,
            role="ai",
            content=ai_text,
        ))
        await self._session.commit()
