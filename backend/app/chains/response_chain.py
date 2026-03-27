"""
Expert Agent 체인 실행 래퍼.
카테고리별 체인 선택, 파싱 실패 방어 로직, 재시도 로직을 포함합니다.
"""
import asyncio
import logging
from typing import Optional

from langchain_core.exceptions import OutputParserException

from app.agents.experts.billing import billing_chain
from app.agents.experts.account import account_chain
from app.agents.experts.technical_support import technical_support_chain
from app.agents.experts.shipping import shipping_chain
from app.agents.fallback import fallback_chain
from app.config.settings import settings
from app.schemas.expert_output import ExpertOutput

logger = logging.getLogger(__name__)

CATEGORY_CHAIN_MAP = {
    "billing": billing_chain,
    "account": account_chain,
    "technical_support": technical_support_chain,
    "shipping": shipping_chain,
}


def _get_chain_for_category(category: str):
    return CATEGORY_CHAIN_MAP.get(category, fallback_chain)


async def run_expert_chain(
    inquiry_text: str,
    category: str,
    retry_count: int = 0,
    chat_history: list = None,
) -> tuple[Optional[ExpertOutput], bool, int]:
    """
    카테고리에 해당하는 Expert Agent 체인을 실행합니다.

    Returns:
        (result, fallback_used, retry_count)
    """
    chain = _get_chain_for_category(category)
    agent_name = f"{category}_expert_agent"

    for attempt in range(settings.max_retry_count + 1):
        try:
            result: ExpertOutput = await chain.ainvoke({
                "inquiry_text": inquiry_text,
                "chat_history": chat_history or [],
            })
            return result, False, retry_count + attempt
        except OutputParserException as e:
            logger.error(
                "Expert chain [%s] output parse failed (attempt %d): %s",
                agent_name, attempt + 1, e
            )
            break
        except asyncio.TimeoutError:
            logger.warning(
                "Expert chain [%s] timed out (attempt %d/%d)",
                agent_name, attempt + 1, settings.max_retry_count + 1
            )
            if attempt < settings.max_retry_count:
                continue
        except Exception as e:
            logger.error(
                "Expert chain [%s] failed (attempt %d): %s",
                agent_name, attempt + 1, e
            )
            if attempt < settings.max_retry_count:
                continue
            break

    # Fallback
    logger.warning("Falling back to fallback_chain for category: %s", category)
    try:
        result = await fallback_chain.ainvoke({
            "inquiry_text": inquiry_text,
            "chat_history": chat_history or [],
        })
        return result, True, retry_count + settings.max_retry_count
    except Exception as e:
        logger.error("Fallback chain also failed: %s", e)
        return None, True, retry_count + settings.max_retry_count
