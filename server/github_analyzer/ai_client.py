from typing import Any, List, Dict
import logging

import asyncio
from openai import AsyncOpenAI, OpenAIError
from server.llm.gateway import openrouter_chat
from server.llm.context import get_llm_stream_context


class ChatClient:
    """AI 聊天客户端，用于与 OpenRouter API 交互"""
    
    ENDPOINT = "https://openrouter.ai/api/v1"

    def __init__(self, options: Dict[str, Any]):
        self.client = AsyncOpenAI(
            api_key=options["api_key"], 
            base_url=ChatClient.ENDPOINT
        )
        self.model = options["model"]

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
        except OpenAIError as e:
            logging.error(f"OpenAI API error: {e}")
            output = ""
        return output

    async def just_chat(self, message: str) -> str:
        """发送单条消息并获取响应"""
        return await self.chat([{"role": "user", "content": message}])
