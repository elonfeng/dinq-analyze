from typing import Any, Dict, List, Optional
import logging

import asyncio

from server.llm.gateway import openrouter_chat
from server.llm.context import get_llm_stream_context


class ChatClient:
    """AI chat client routed through DINQ LLM gateway."""

    def __init__(self, options: Dict[str, Any]):
        model = options.get("model") if isinstance(options, dict) else None
        self.model: Optional[str] = str(model).strip() if model else None

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """发送聊天消息并获取响应"""
        try:
            callback, force_stream = get_llm_stream_context()
            # Route through LLM gateway for caching/repair; run in thread to avoid blocking loop.
            output = await asyncio.to_thread(
                openrouter_chat,
                task="github_ai",
                messages=messages,
                model=self.model,
                stream=force_stream,
                stream_callback=callback,
            )
        except Exception as e:  # noqa: BLE001
            logging.error(f"LLM error: {e}")
            output = ""
        return output

    async def just_chat(self, message: str) -> str:
        """发送单条消息并获取响应"""
        return await self.chat([{"role": "user", "content": message}])
