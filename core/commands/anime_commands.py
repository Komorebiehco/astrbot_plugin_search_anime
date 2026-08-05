from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.message_components import Plain

from ..services.saucenao import search_illust_saucenao
from ..services.trace_moe import search_anime_trace_moe
from ..utils.image_extractor import extract_image_info


async def execute_search_anime_command(plugin, event: AstrMessageEvent):
    """Execute /search_anime command handler."""
    image_url, image_bytes = await extract_image_info(event)
    if not (image_url or image_bytes):
        yield MessageChain(
            [
                Plain(
                    "🧐 未找到图片，请在发送指令时附带图片、引用包含图片的回复，或提供图片 URL 喵。"
                )
            ]
        )
        return

    default_limit = 3
    if hasattr(plugin, "config") and plugin.config:
        default_limit = int(plugin.config.get("default_limit", 3))

    target_limit = default_limit
    raw_str = getattr(event, "message_str", "") or ""
    words = raw_str.strip().split()
    for w in reversed(words):
        if w.isdigit() and int(w) > 0:
            target_limit = min(max(1, int(w)), 10)
            break

    bot_id = event.get_self_id()
    bot_name = event.get_sender_name() or "AstrBot"

    ok, chain, summary_str = await search_anime_trace_moe(
        image_url=image_url,
        image_bytes=image_bytes,
        limit=target_limit,
        bot_id=bot_id,
        bot_name=bot_name,
    )

    yield chain


async def execute_search_illust_command(plugin, event: AstrMessageEvent):
    """Execute /search_illust command handler."""
    image_url, image_bytes = await extract_image_info(event)
    if not (image_url or image_bytes):
        yield MessageChain(
            [
                Plain(
                    "🧐 未找到图片，请在发送指令时附带图片、引用包含图片的回复，或提供图片 URL 喵。"
                )
            ]
        )
        return

    api_key = ""
    default_limit = 3
    if hasattr(plugin, "config") and plugin.config:
        api_key = plugin.config.get("saucenao_api_key", "")
        default_limit = int(plugin.config.get("default_limit", 3))

    target_limit = default_limit
    raw_str = getattr(event, "message_str", "") or ""
    words = raw_str.strip().split()
    for w in reversed(words):
        if w.isdigit() and int(w) > 0:
            target_limit = min(max(1, int(w)), 10)
            break

    bot_id = event.get_self_id()
    bot_name = event.get_sender_name() or "AstrBot"

    ok, chain, summary_str = await search_illust_saucenao(
        image_url=image_url,
        image_bytes=image_bytes,
        limit=target_limit,
        api_key=api_key,
        bot_id=bot_id,
        bot_name=bot_name,
    )

    yield chain
