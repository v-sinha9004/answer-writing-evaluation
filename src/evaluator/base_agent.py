"""Base agent class with async client, structured schema parsing, and retry handling."""

import os
import time
from typing import Type, TypeVar, Optional, Any
from pydantic import BaseModel
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.config import OPENAI_API_KEY

from src.evaluator.schemas import TokenUsage

T = TypeVar("T", bound=BaseModel)


class BaseAgent:
    """Base class for isolated specialist evaluator agents."""

    def __init__(self, model: Optional[str] = None, client: Optional[AsyncOpenAI] = None):
        self.client = client or AsyncOpenAI(api_key=OPENAI_API_KEY or "sk-dummy-key-for-testing")
        self.model = model or os.getenv("EVALUATION_MODEL", "gpt-4o")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=6),
        reraise=True,
    )
    async def run_structured_with_usage(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Type[T],
        temperature: float = 0.1,
    ) -> tuple[T, TokenUsage]:
        """Call LLM with structured output adhering to response_format and return TokenUsage."""
        response = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=response_format,
            temperature=temperature,
        )
        usage = TokenUsage()
        if hasattr(response, "usage") and response.usage:
            usage = TokenUsage(
                prompt_tokens=getattr(response.usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(response.usage, "completion_tokens", 0) or 0,
                total_tokens=getattr(response.usage, "total_tokens", 0) or 0,
            )
        return response.choices[0].message.parsed, usage

    async def run_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Type[T],
        temperature: float = 0.1,
    ) -> T:
        """Call LLM with guaranteed structured output adhering to response_format."""
        parsed, _ = await self.run_structured_with_usage(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format=response_format,
            temperature=temperature,
        )
        return parsed
