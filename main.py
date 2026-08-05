from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star
from astrbot.core.message.message_event_result import MessageEventResult
from astrbot.core.provider.register import llm_tools
from astrbot.core.star.star_tools import StarTools

from .core.commands import (
    execute_search_anime_command,
    execute_search_illust_command,
)
from .core.llm_tools import (
    execute_search_image_tool,
)


class SearchAnimePlugin(Star):
    """AstrBot plugin for searching anime (trace.moe) and illustrations (SauceNAO)."""

    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}
        self._apply_llm_tool_config()

    @filter.on_plugin_loaded()
    async def on_loaded(self, _):
        self._apply_llm_tool_config()

    def _apply_llm_tool_config(self):
        tool_name = "search_image"
        enable_tool = bool(self.config.get("enable_llm_tool", True))
        giftia_mode = bool(self.config.get("enable_giftia_mode", False))

        # 1. Enable / Disable LLM tool activation
        try:
            if enable_tool:
                StarTools.activate_llm_tool(tool_name)
            else:
                StarTools.deactivate_llm_tool(tool_name)
        except Exception as e:
            logger.warning(f"[search_anime] Failed to toggle LLM tool state: {e}")

        # 2. Determine URL parameter description based on Giftia mode
        url_desc = (
            "Image hash."
            if giftia_mode
            else "Target image HTTP/HTTPS URL or local file path."
        )
        type_desc = "Search type: 'anime' for anime scene screenshots, 'illust' for illustration/artwork sources."
        limit_desc = "Optional candidate results limit (1-10)."
        tool_desc = "Search for anime scene info or illustration source from an image."

        # 3. Update tool and parameter descriptions in global llm_tools registry & context tool manager
        try:
            tool_managers = [llm_tools]
            tool_mgr_ctx = getattr(self.context, "get_llm_tool_manager", None)
            if callable(tool_mgr_ctx):
                ctx_mgr = tool_mgr_ctx()
                if ctx_mgr:
                    tool_managers.append(ctx_mgr)

            for mgr in tool_managers:
                if hasattr(mgr, "func_list"):
                    for ft in mgr.func_list:
                        if getattr(ft, "name", None) == tool_name:
                            ft.description = tool_desc
                            props = getattr(ft, "parameters", {}).get("properties", {})
                            if "type" in props:
                                props["type"]["description"] = type_desc
                            if "url" in props:
                                props["url"]["description"] = url_desc
                            if "limit" in props:
                                props["limit"]["description"] = limit_desc

            # 4. Update Handler metadata description for Dashboard WebUI display
            from astrbot.core.star.star_handler import star_handlers_registry

            full_webui_desc = f"{tool_desc} Args: type (str): {type_desc} url (str): {url_desc} limit (int): {limit_desc}"

            for md in star_handlers_registry:
                if md.handler_name == tool_name:
                    md.desc = full_webui_desc
                    break
        except Exception as e:
            logger.warning(
                f"[search_anime] Failed to update LLM tool descriptions: {e}"
            )

    # ==================== LLM Tools ====================

    @filter.llm_tool(name="search_image")
    async def search_image(
        self,
        event: AstrMessageEvent,
        type: str,
        url: str,
        limit: int | None = None,
    ) -> str:
        """Search for anime scene info or illustration source from an image.

        Args:
            type (str): Search type: 'anime' for anime scene screenshots, 'illust' for illustration/artwork sources.
            url (str): Target image HTTP/HTTPS URL, local file path, or image hash.
            limit (int): Optional candidate results limit (1-10).

        Returns:
            str: Summary of search results.
        """
        summary_result = ""
        try:
            async for chain, summary_str in execute_search_image_tool(
                self, event, type=type, url=url, limit=limit
            ):
                if chain:
                    if isinstance(chain, MessageChain):
                        await event.send(chain)
                    elif isinstance(chain, MessageEventResult):
                        event.set_result(chain)
                summary_result = summary_str
        except Exception as e:
            logger.error(
                f"[search_anime] LLM Tool search_image failed: {e}", exc_info=True
            )
            summary_result = f"以图搜图发生异常: {e}"
        return summary_result

    # ==================== Slash Commands ====================

    @filter.command("search_anime", alias={"sa", "搜番", "以图搜番", "找番", "搜动画"})
    async def search_anime_cmd(self, event: AstrMessageEvent):
        """以图搜番指令。使用方法: /搜番 或 /sa [图片URL/路径/media_id] [数量] 或直接发送/回复图片。"""
        try:
            async for result in execute_search_anime_command(self, event):
                if result:
                    if isinstance(result, MessageChain):
                        yield event.chain_result(result.chain)
                    elif isinstance(result, MessageEventResult):
                        yield result
        except Exception as e:
            logger.error(
                f"[search_anime] Command search_anime_cmd exception: {e}", exc_info=True
            )
            yield event.plain_result(f"搜番失败: {e}")

    @filter.command(
        "search_illust",
        alias={"si", "搜插画", "搜图", "以图搜图", "找插画", "搜画", "搜来源"},
    )
    async def search_illust_cmd(self, event: AstrMessageEvent):
        """以图搜插画/搜图指令。使用方法: /搜插画 或 /si [图片URL/路径/media_id] [数量] 或直接发送/回复图片。"""
        try:
            async for result in execute_search_illust_command(self, event):
                if result:
                    if isinstance(result, MessageChain):
                        yield event.chain_result(result.chain)
                    elif isinstance(result, MessageEventResult):
                        yield result
        except Exception as e:
            logger.error(
                f"[search_anime] Command search_illust_cmd exception: {e}",
                exc_info=True,
            )
            yield event.plain_result(f"搜插画失败: {e}")
