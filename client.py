from __future__ import annotations

import base64
import binascii
import inspect
from typing import Any, Awaitable, Callable, TypedDict, cast

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover - optional dependency at runtime
    AsyncOpenAI = None  # type: ignore[assignment]

from config import Settings


class ImageInput(TypedDict):
    mime_type: str
    data_b64: str


class ChatMessage(TypedDict, total=False):
    role: str
    content: str
    images: list[ImageInput]


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.nvidia_client = (
            AsyncOpenAI(
                api_key=settings.nvidia_api_key,
                base_url="https://integrate.api.nvidia.com/v1"
            )
            if settings.nvidia_api_key and AsyncOpenAI is not None
            else None
        )

    async def aclose(self) -> None:
        if self.nvidia_client and hasattr(self.nvidia_client, "close"):
            maybe_awaitable = self.nvidia_client.close()
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable

    async def generate(self, messages: list[ChatMessage]) -> str:
        if AsyncOpenAI is None:
            raise RuntimeError("OpenAI SDK not installed. Run: pip install -r requirements.txt")
        if self.nvidia_client is None:
            raise RuntimeError("Missing NVIDIA_API_KEY")

        chat_completion = await self.nvidia_client.chat.completions.create(
            model=self.settings.nvidia_model,
            messages=self._build_openai_style_messages(messages),
            max_tokens=self.settings.nvidia_max_tokens,
            temperature=self.settings.temperature,
            top_p=self.settings.nvidia_top_p,
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": self.settings.nvidia_enable_thinking,
                }
            },
        )
        message = chat_completion.choices[0].message
        content = message.content
        if isinstance(content, str) and content.strip():
            return content.strip()
        raise RuntimeError("NVIDIA returned an empty response.")

    async def approve_call_name(self, field_name: str, value: str) -> bool:
        """Simplified approval: always approve since Gemini moderator is removed."""
        return True

    def _build_openai_style_messages(
        self,
        messages: list[ChatMessage],
    ) -> list[dict[str, Any]]:
        openai_messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.settings.system_prompt}
        ]
        for msg in messages:
            text = msg.get("content", "").strip()
            images = msg.get("images", [])
            if images:
                parts: list[dict[str, Any]] = []
                if text:
                    parts.append({"type": "text", "text": text})
                for image in images:
                    data_url = f"data:{image['mime_type']};base64,{image['data_b64']}"
                    parts.append({
                        "type": "image_url", 
                        "image_url": {
                            "url": data_url,
                            "detail": "high"
                        }
                    })
                openai_messages.append({"role": msg["role"], "content": parts})
            elif text:
                openai_messages.append({"role": msg["role"], "content": text})
        return openai_messages
