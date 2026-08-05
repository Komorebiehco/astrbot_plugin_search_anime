from collections.abc import AsyncGenerator
from typing import Any

from astrbot.api.event import AstrMessageEvent

from ..services.saucenao import search_illust_saucenao
from ..services.trace_moe import search_anime_trace_moe
from ..utils.image_extractor import extract_image_info


async def execute_search_image_tool(
    plugin,
    event: AstrMessageEvent,
    type: str,
    url: str,
    limit: int | None = None,
) -> AsyncGenerator[tuple[Any, str], None]:
    """Execute search_image LLM tool logic.

    Args:
        plugin: Plugin instance.
        event: AstrMessageEvent object.
        type: Search target ('anime' or 'illust').
        url: Image URL, local file path, or image hash.
        limit: Optional results limit.

    Yields:
        Yields (message_chain_or_none, summary_str) tuple.
    """
    image_url, image_bytes = await extract_image_info(event, url_param=url)
    if not (image_url or image_bytes):
        err_msg = "🧐 未找到要检索的图片。请提供图片地址、本地路径或图片哈希值。"
        yield (
            event.plain_result(err_msg),
            "Failed to search image: No valid image target provided.",
        )
        return

    api_key = ""
    default_limit = 3
    llm_only = False
    if hasattr(plugin, "config") and plugin.config:
        api_key = plugin.config.get("saucenao_api_key", "")
        default_limit = int(plugin.config.get("default_limit", 3))
        llm_only = bool(plugin.config.get("enable_llm_only_mode", False))

    target_limit = limit if (limit is not None and limit > 0) else default_limit
    bot_id = event.get_self_id()
    bot_name = event.get_sender_name() or "AstrBot"

    search_type_clean = (type or "").strip().lower()

    if search_type_clean == "illust":
        ok, chain, summary_str = await search_illust_saucenao(
            image_url=image_url,
            image_bytes=image_bytes,
            limit=target_limit,
            api_key=api_key,
            bot_id=bot_id,
            bot_name=bot_name,
        )
    else:  # default to anime for 'anime' or fallback
        ok, chain, summary_str = await search_anime_trace_moe(
            image_url=image_url,
            image_bytes=image_bytes,
            limit=target_limit,
            bot_id=bot_id,
            bot_name=bot_name,
        )

    if llm_only:
        yield None, summary_str
    else:
        if ok:
            completion_msg = "搜图成功，富文本结果卡片已直接发送至当前聊天窗口。"
        else:
            completion_msg = summary_str
        yield chain, completion_msg
