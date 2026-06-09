import abc
import asyncio
import os
import re
from typing import List, Dict
import httpx
from openai import AsyncOpenAI
from google import genai
from google.genai import types

class BaseAgent(abc.ABC):
    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        pass

    def _prepare_output(self, text: str) -> str:
        return text

class TheMind(BaseAgent):
    """GPT-5.5 (OpenAI) - The Strategic Thinker"""
    def __init__(self, api_key: str):
        super().__init__("TheMind")
        self.client = AsyncOpenAI(api_key=api_key)

    async def chat(self, messages: List[Dict[str, str]], reasoning_effort: str | None = None) -> str:
        request = dict(
            model="gpt-5.5",
            input=messages,
            max_output_tokens=1024,
        )
        if reasoning_effort:
            request["reasoning"] = {"effort": reasoning_effort}
        response = await self.client.responses.create(**request)
        return self._prepare_output(getattr(response, "output_text", "") or "")

class TheSenses(BaseAgent):
    """Gemini (Google) - The Observer"""
    def __init__(self, api_key: str, model: str | None = None):
        super().__init__("TheSenses")
        self.client = genai.Client(api_key=api_key)
        self.model = model or os.getenv("GEMINI_FLASH_MODEL", "gemini-3.1-flash")

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        prompt = "\n".join(
            f"{item.get('role', 'user').upper()}: {item.get('content', '').strip()}"
            for item in messages
            if item.get("content")
        )
        timeout = float(os.getenv("GEMINI_TEXT_TIMEOUT_SECONDS", "45"))
        response = await asyncio.wait_for(
            self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
            ),
            timeout=timeout,
        )
        return self._prepare_output(getattr(response, "text", "") or "")

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        timeout = float(os.getenv("GEMINI_VISION_TIMEOUT_SECONDS", "45"))
        response = await asyncio.wait_for(
            self.client.aio.models.generate_content(
                model=self.model,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                ],
            ),
            timeout=timeout,
        )
        return self._prepare_output(getattr(response, "text", "") or "")

class TheSteward(BaseAgent):
    """Claude (Anthropic) - The Careful Reviewer"""
    def __init__(self, api_key: str, model: str | None = None):
        super().__init__("TheSteward")
        self.api_key = api_key
        self.model = model or os.getenv("CLAUDE_STEWARD_MODEL", "claude-opus-4-8")

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        system_parts = [item.get("content", "") for item in messages if item.get("role") == "system"]
        user_parts = [item.get("content", "") for item in messages if item.get("role") != "system"]
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": "\n\n".join(system_parts) or "You are Maya's careful review lane.",
            "messages": [{"role": "user", "content": "\n\n".join(user_parts)}],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            if response.is_error:
                request_id = response.headers.get("request-id") or response.headers.get("x-request-id") or ""
                detail = _safe_provider_error(response.text)
                raise httpx.HTTPStatusError(
                    f"Anthropic error {response.status_code}"
                    f"{f' request_id={request_id}' if request_id else ''}: {detail}",
                    request=response.request,
                    response=response,
                )
        data = response.json()
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        return self._prepare_output(text)


def _safe_provider_error(text: str) -> str:
    cleaned = re.sub(r"sk-[A-Za-z0-9_\\-]+", "<redacted-key>", text or "")
    cleaned = re.sub(r"Bearer\\s+[A-Za-z0-9_.\\-]+", "Bearer <redacted>", cleaned)
    return " ".join(cleaned.split())[:600] or "no response body"

class TheNews(BaseAgent):
    """Grok/XAI - The Real-time Pulse"""
    def __init__(self, api_key: str):
        super().__init__("TheNews")
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        self.model = os.getenv("XAI_TEXT_MODEL", "grok-4.3")

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        return self._prepare_output(response.choices[0].message.content)
