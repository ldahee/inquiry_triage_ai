from typing import Any, Optional
from typing_extensions import TypedDict


class ExecutionTraceItem(TypedDict, total=False):
    node_name: str
    status: str
    duration_ms: Optional[int]


class InquiryState(TypedDict):
    # Input
    inquiry_text: str
    user_id: Optional[str]
    channel: Optional[str]
    locale: Optional[str]
    inquiry_id: Optional[str]

    # Conversation
    conversation_id: Optional[str]
    chat_history: list[Any]  # list[BaseMessage]

    # Routing
    category: Optional[str]
    confidence: Optional[float]
    routing_reason: Optional[str]
    selected_agent: Optional[str]

    # Response
    answer: Optional[str]

    # Safety
    safety_flag: Optional[bool]

    # Control
    fallback_used: bool
    retry_count: int
    llm_call_count: int
    error: Optional[str]

    # Execution trace
    execution_trace: list[ExecutionTraceItem]
