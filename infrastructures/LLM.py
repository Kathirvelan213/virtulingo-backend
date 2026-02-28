"""
Ollama (Local Llama 3) Implementation of ILargeLanguageModel.

Uses Ollama REST API for local inference.
Supports streaming and one-shot generation.
"""

import os
from typing import AsyncGenerator

import httpx

from domain.interfaces.ILargeLanguageModel import ILargeLanguageModel


class OllamaLLM(ILargeLanguageModel):
    def __init__(self):
        self._base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self._model = os.environ.get("OLLAMA_MODEL", "llama3")

    async def complete(self, system_prompt: str, user_message: str) -> str:
        """
        One-shot completion.
        Used for grammar correction (JSON output).
        """
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": self._build_prompt(system_prompt, user_message),
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                    },
                    # Forces JSON-like structured output (best-effort)
                    "format": "json",
                },
            )

            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()

    async def stream_complete(
        self, system_prompt: str, user_message: str
    ) -> AsyncGenerator[str, None]:
        """
        Streaming completion.
        Used for NPC conversation replies piped to TTS.
        """
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": self._build_prompt(system_prompt, user_message),
                    "stream": True,
                    "options": {
                        "temperature": 0.8,
                    },
                },
            ) as response:

                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    data = httpx.Response(200, content=line).json()
                    chunk = data.get("response")

                    if chunk:
                        yield chunk

    def _build_prompt(self, system_prompt: str, user_message: str) -> str:
        """
        Formats conversation into a single prompt.
        Ollama does not use ChatCompletion-style role messages,
        so we manually structure it.
        """
        return (
            f"### System:\n{system_prompt}\n\n"
            f"### User:\n{user_message}\n\n"
            f"### Assistant:\n"
        )