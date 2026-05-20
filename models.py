import abc
import os
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
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        return self._prepare_output(getattr(response, "text", "") or "")

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            ],
        )
        return self._prepare_output(getattr(response, "text", "") or "")

class TheHands(BaseAgent):
    """Kimi/OpenAI - The Executor"""
    def __init__(self, api_key: str, base_url: str = "https://api.moonshot.ai/v1"):
        super().__init__("TheHands")
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        response = await self.client.chat.completions.create(
            model="kimi-k2.6",
            messages=messages
        )
        return self._prepare_output(response.choices[0].message.content)

class TheSteward(BaseAgent):
    """Claude (Anthropic) - The Careful Reviewer"""
    def __init__(self, api_key: str, model: str | None = None):
        super().__init__("TheSteward")
        self.api_key = api_key
        self.model = model or os.getenv("CLAUDE_STEWARD_MODEL", "claude-sonnet-4-6")

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
            response.raise_for_status()
        data = response.json()
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        return self._prepare_output(text)

class TheNews(BaseAgent):
    """Grok/XAI - The Real-time Pulse"""
    def __init__(self, api_key: str):
        super().__init__("TheNews")
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        response = await self.client.chat.completions.create(
            model="grok-beta",
            messages=messages
        )
        return self._prepare_output(response.choices[0].message.content)
