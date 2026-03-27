"""
LangGraph 기반 문의 처리 상태 그래프.

노드 흐름:
  input_node → safety_check_node → router_node → [expert_node | fallback_node | safe_response_node]
             → response_finalize_node → END
"""
import logging
import time
from typing import Literal

from langgraph.graph import StateGraph, END

from app.agents.safety import safety_chain, SAFETY_BLOCKED_RESPONSE
from app.chains.router_chain import run_router_chain
from app.chains.response_chain import run_expert_chain, fallback_chain
from app.config.settings import settings
from app.schemas.inquiry_state import InquiryState

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 노드 함수
# ──────────────────────────────────────────────

async def input_node(state: InquiryState) -> dict:
    """입력 검증 및 inquiry_id 확인."""
    inquiry_id = state["inquiry_id"]  # 서비스 레이어에서 항상 생성하여 전달
    logger.info("[%s] input_node: received inquiry", inquiry_id)
    return {
        "inquiry_id": inquiry_id,
        "fallback_used": False,
        "retry_count": 0,
        "llm_call_count": 0,
        "execution_trace": [
            {"node_name": "input_node", "status": "completed", "duration_ms": 0}
        ],
    }


async def safety_check_node(state: InquiryState) -> dict:
    """Safety Agent를 통해 정책 위반 여부를 확인합니다."""
    inquiry_id = state["inquiry_id"]
    start = time.monotonic()
    logger.info("[%s] safety_check_node: running safety check", inquiry_id)

    trace = list(state.get("execution_trace", []))
    try:
        result = await safety_chain.ainvoke({"inquiry_text": state["inquiry_text"]})
        is_safe = result.is_safe
    except Exception as e:
        logger.error("[%s] safety_check_node failed: %s — blocking as unsafe (fail-closed)", inquiry_id, e)
        is_safe = False  # 안전 판단 실패 시 차단 (fail-closed)

    duration_ms = int((time.monotonic() - start) * 1000)
    trace.append({
        "node_name": "safety_check_node",
        "status": "completed",
        "duration_ms": duration_ms,
    })
    return {
        "safety_flag": not is_safe,
        "llm_call_count": state.get("llm_call_count", 0) + 1,
        "execution_trace": trace,
    }


async def safe_response_node(state: InquiryState) -> dict:
    """정책 위반 요청에 대해 안전 응답을 반환합니다."""
    inquiry_id = state["inquiry_id"]
    logger.info("[%s] safe_response_node: returning safety blocked response", inquiry_id)
    trace = list(state.get("execution_trace", []))
    trace.append({"node_name": "safe_response_node", "status": "completed", "duration_ms": 0})
    return {
        "answer": SAFETY_BLOCKED_RESPONSE,
        "category": "safety",
        "confidence": 1.0,
        "selected_agent": "safety_agent",
        "execution_trace": trace,
    }


async def router_node(state: InquiryState) -> dict:
    """Router Agent를 통해 문의를 분류합니다."""
    inquiry_id = state["inquiry_id"]
    start = time.monotonic()
    logger.info("[%s] router_node: routing inquiry", inquiry_id)

    trace = list(state.get("execution_trace", []))
    result = await run_router_chain(state["inquiry_text"], chat_history=state.get("chat_history", []))
    duration_ms = int((time.monotonic() - start) * 1000)

    if result is None:
        logger.warning("[%s] router_node: parse failed, will fallback", inquiry_id)
        trace.append({
            "node_name": "router_node",
            "status": "parse_failed",
            "duration_ms": duration_ms,
        })
        return {
            "category": "general",
            "confidence": 0.0,
            "routing_reason": "Router output parse failed",
            "llm_call_count": state.get("llm_call_count", 0) + 1,
            "error": "OUTPUT_PARSE_FAILED",
            "execution_trace": trace,
        }

    trace.append({
        "node_name": "router_node",
        "status": "completed",
        "duration_ms": duration_ms,
    })
    logger.info(
        "[%s] router_node: category=%s confidence=%.2f",
        inquiry_id, result.category, result.confidence
    )
    return {
        "category": result.category,
        "confidence": result.confidence,
        "routing_reason": result.routing_reason,
        "llm_call_count": state.get("llm_call_count", 0) + 1,
        "execution_trace": trace,
    }


async def _run_expert_node(state: InquiryState, agent_name: str) -> dict:
    """Expert Agent 노드 공통 실행 로직."""
    inquiry_id = state["inquiry_id"]
    category = state["category"]
    start = time.monotonic()
    logger.info("[%s] %s: generating answer", inquiry_id, agent_name)

    trace = list(state.get("execution_trace", []))

    if state.get("llm_call_count", 0) >= settings.max_llm_calls:
        logger.warning("[%s] max_llm_calls reached, forcing fallback", inquiry_id)
        trace.append({"node_name": agent_name, "status": "skipped_max_calls", "duration_ms": 0})
        return {
            "selected_agent": "general_fallback_agent",
            "fallback_used": True,
            "execution_trace": trace,
        }

    result, fallback_used, new_retry = await run_expert_chain(
        inquiry_text=state["inquiry_text"],
        category=category,
        retry_count=state.get("retry_count", 0),
        chat_history=state.get("chat_history", []),
    )
    duration_ms = int((time.monotonic() - start) * 1000)

    selected_agent = "general_fallback_agent" if fallback_used else agent_name
    status = "fallback" if fallback_used else "completed"
    trace.append({"node_name": agent_name, "status": status, "duration_ms": duration_ms})

    if result is None:
        logger.error("[%s] %s: all chains failed", inquiry_id, agent_name)
        return {
            "selected_agent": selected_agent,
            "fallback_used": True,
            "retry_count": new_retry,
            "llm_call_count": state.get("llm_call_count", 0) + 1,
            "error": "AGENT_EXECUTION_FAILED",
            "execution_trace": trace,
        }

    return {
        "answer": result.answer,
        "selected_agent": selected_agent,
        "fallback_used": fallback_used,
        "retry_count": new_retry,
        "llm_call_count": state.get("llm_call_count", 0) + 1,
        "execution_trace": trace,
    }


async def billing_agent_node(state: InquiryState) -> dict:
    return await _run_expert_node(state, "billing_expert_agent")


async def account_agent_node(state: InquiryState) -> dict:
    return await _run_expert_node(state, "account_expert_agent")


async def technical_support_agent_node(state: InquiryState) -> dict:
    return await _run_expert_node(state, "technical_support_expert_agent")


async def shipping_agent_node(state: InquiryState) -> dict:
    return await _run_expert_node(state, "shipping_expert_agent")


async def fallback_agent_node(state: InquiryState) -> dict:
    """Fallback Agent 노드."""
    inquiry_id = state["inquiry_id"]
    start = time.monotonic()
    logger.info("[%s] fallback_agent_node: generating fallback answer", inquiry_id)

    trace = list(state.get("execution_trace", []))
    try:
        result = await fallback_chain.ainvoke({
            "inquiry_text": state["inquiry_text"],
            "chat_history": state.get("chat_history", []),
        })
        answer = result.answer
        status = "completed"
    except Exception as e:
        logger.error("[%s] fallback_agent_node failed: %s", inquiry_id, e)
        answer = "죄송합니다. 현재 문의를 처리하지 못했습니다. 잠시 후 다시 시도해 주세요."
        status = "error"

    duration_ms = int((time.monotonic() - start) * 1000)
    trace.append({"node_name": "fallback_agent_node", "status": status, "duration_ms": duration_ms})
    return {
        "answer": answer,
        "selected_agent": "general_fallback_agent",
        "fallback_used": True,
        "llm_call_count": state.get("llm_call_count", 0) + 1,
        "execution_trace": trace,
    }


async def response_finalize_node(state: InquiryState) -> dict:
    """최종 응답을 정리합니다."""
    inquiry_id = state["inquiry_id"]
    logger.info("[%s] response_finalize_node: finalizing", inquiry_id)
    trace = list(state.get("execution_trace", []))
    trace.append({"node_name": "response_finalize_node", "status": "completed", "duration_ms": 0})

    if not state.get("answer"):
        return {
            "answer": "죄송합니다. 현재 문의를 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            "error": state.get("error") or "INTERNAL_ERROR",
            "execution_trace": trace,
        }
    return {"execution_trace": trace}


# ──────────────────────────────────────────────
# 조건 분기 함수
# ──────────────────────────────────────────────

def route_after_safety(state: InquiryState) -> Literal["safe_response_node", "router_node"]:
    if state.get("safety_flag"):
        return "safe_response_node"
    return "router_node"


def route_after_router(
    state: InquiryState,
) -> Literal[
    "billing_agent_node",
    "account_agent_node",
    "technical_support_agent_node",
    "shipping_agent_node",
    "fallback_agent_node",
]:
    confidence = state.get("confidence", 0.0)
    category = state.get("category", "general")

    if confidence < settings.routing_confidence_low_threshold:
        return "fallback_agent_node"

    routing_map = {
        "billing": "billing_agent_node",
        "account": "account_agent_node",
        "technical_support": "technical_support_agent_node",
        "shipping": "shipping_agent_node",
    }
    return routing_map.get(category, "fallback_agent_node")


# ──────────────────────────────────────────────
# 그래프 빌드
# ──────────────────────────────────────────────

def build_inquiry_graph():
    graph = StateGraph(InquiryState)

    # 노드 등록
    graph.add_node("input_node", input_node)
    graph.add_node("safety_check_node", safety_check_node)
    graph.add_node("safe_response_node", safe_response_node)
    graph.add_node("router_node", router_node)
    graph.add_node("billing_agent_node", billing_agent_node)
    graph.add_node("account_agent_node", account_agent_node)
    graph.add_node("technical_support_agent_node", technical_support_agent_node)
    graph.add_node("shipping_agent_node", shipping_agent_node)
    graph.add_node("fallback_agent_node", fallback_agent_node)
    graph.add_node("response_finalize_node", response_finalize_node)

    # 엣지 연결
    graph.set_entry_point("input_node")
    graph.add_edge("input_node", "safety_check_node")

    graph.add_conditional_edges(
        "safety_check_node",
        route_after_safety,
        {
            "safe_response_node": "safe_response_node",
            "router_node": "router_node",
        },
    )

    graph.add_conditional_edges(
        "router_node",
        route_after_router,
        {
            "billing_agent_node": "billing_agent_node",
            "account_agent_node": "account_agent_node",
            "technical_support_agent_node": "technical_support_agent_node",
            "shipping_agent_node": "shipping_agent_node",
            "fallback_agent_node": "fallback_agent_node",
        },
    )

    for node in [
        "safe_response_node",
        "billing_agent_node",
        "account_agent_node",
        "technical_support_agent_node",
        "shipping_agent_node",
        "fallback_agent_node",
    ]:
        graph.add_edge(node, "response_finalize_node")

    graph.add_edge("response_finalize_node", END)

    return graph.compile()


inquiry_graph = build_inquiry_graph()
