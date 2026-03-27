"""
Router Agent 체인 실행 래퍼.
파싱 실패 방어 로직과 LLM 호출 카운트 관리를 포함합니다.
"""
import logging
from typing import Optional

from langchain_core.exceptions import OutputParserException

from app.agents.router import router_chain
from app.schemas.router_output import RouterOutput

logger = logging.getLogger(__name__)


async def run_router_chain(inquiry_text: str, chat_history: list = None) -> Optional[RouterOutput]:
    """
    Router Agent 체인을 실행합니다.
    파싱 실패 시 None을 반환합니다.
    """
    try:
        result: RouterOutput = await router_chain.ainvoke({
            "inquiry_text": inquiry_text,
            "chat_history": chat_history or [],
        })
        return result
    except OutputParserException as e:
        logger.error("Router chain output parse failed: %s", e)
        return None
    except Exception as e:
        logger.error("Router chain execution failed: %s", e)
        return None
