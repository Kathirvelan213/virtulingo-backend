"""
Google Gemini Implementation of ILargeLanguageModel.

Uses the modern google.genai SDK (2025+).
Supports streaming and structured output (JSON).

Free tier: Get API key from https://aistudio.google.com
Env var: GOOGLE_API_KEY or GEMINI_API_KEY
"""

import os
import asyncio
from typing import AsyncGenerator

from google import genai
from google.genai.errors import ServerError

from domain.interfaces.ILargeLanguageModel import ILargeLanguageModel


class GeminiLLM(ILargeLanguageModel):
    def __init__(self):
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY or GEMINI_API_KEY must be set. "
                "Get a free key at https://aistudio.google.com"
            )
        
        # Initialize client without timeout to use library defaults
        self._client = genai.Client(api_key=api_key)
        self._model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        print(f"[GeminiLLM] Initialized with model: {self._model_name}")

    async def _retry_with_backoff(self, func, *args, max_retries=2, **kwargs):
        """Retry API calls with exponential backoff for 503 errors."""
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except ServerError as e:
                if e.status_code == 503 and attempt < max_retries:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s...
                    print(f"[GeminiLLM] 503 error, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    raise

    async def complete(self, system_prompt: str, user_message: str) -> str:
        """
        One-shot completion with structured output.
        Used for grammar correction (JSON format).
        """
        prompt = f"{system_prompt}\n\nUser input: {user_message}"
        
        response = await self._retry_with_backoff(
            self._client.models.generate_content,
            model=self._model_name,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            )
        )
        
        return response.text.strip()

    async def stream_complete(
        self, system_prompt: str, user_message: str
    ) -> AsyncGenerator[str, None]:
        """
        Streaming completion for conversational responses.
        Used for NPC dialogue generation.
        """
        prompt = f"{system_prompt}\n\nUser: {user_message}\nAssistant:"
        
        print(f"[GeminiLLM] Starting streaming generation...")
        
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = self._client.models.generate_content_stream(
                    model=self._model_name,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        temperature=0.8,
                    )
                )
                
                for chunk in response:
                    if chunk.text:
                        print(f"[GeminiLLM] Yielding chunk: '{chunk.text[:50]}...'")
                        yield chunk.text
                
                # Successful completion, exit retry loop
                break
                
            except ServerError as e:
                if e.status_code == 503 and attempt < max_retries:
                    wait_time = 2 ** attempt
                    print(f"[GeminiLLM] 503 error in streaming, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"[GeminiLLM] ❌ Gemini API unavailable after {attempt + 1} attempts")
                    raise Exception(
                        f"Gemini API is experiencing high demand. "
                        f"Please try again in a few moments. (Model: {self._model_name})"
                    )


class GeminiLLMConfigurable(ILargeLanguageModel):
    """
    Configurable variant of GeminiLLM for fine-tuned control.
    """
    
    def __init__(
        self,
        temperature: float = 0.7,
        top_p: float = 0.95,
        top_k: int = 40,
        max_output_tokens: int = 2048,
    ):
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY or GEMINI_API_KEY must be set. "
                "Get a free key at https://aistudio.google.com"
            )
        
        self._client = genai.Client(api_key=api_key)
        self._model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        self._temperature = temperature
        self._top_p = top_p
        self._top_k = top_k
        self._max_output_tokens = max_output_tokens

    async def complete(self, system_prompt: str, user_message: str) -> str:
        prompt = f"{system_prompt}\n\nUser input: {user_message}"
        
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=self._temperature,
                top_p=self._top_p,
                top_k=self._top_k,
                max_output_tokens=self._max_output_tokens,
                response_mime_type="application/json",
            )
        )
        
        return response.text.strip()

    async def stream_complete(
        self, system_prompt: str, user_message: str
    ) -> AsyncGenerator[str, None]:
        prompt = f"{system_prompt}\n\nUser: {user_message}\nAssistant:"
        
        response = self._client.models.generate_content_stream(
            model=self._model_name,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=self._temperature,
                top_p=self._top_p,
                top_k=self._top_k,
                max_output_tokens=self._max_output_tokens,
            )
        )
        
        for chunk in response:
            if chunk.text:
                yield chunk.text
