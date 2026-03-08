"""
Groq LLM Implementation.

Uses Groq's ultra-fast inference API for LLM completions.
Supports streaming and JSON mode for structured outputs.

Free tier: Get API key from https://console.groq.com
Env var: GROQ_API_KEY
"""

import os
import asyncio
from typing import AsyncGenerator

from groq import Groq

from domain.interfaces.ILargeLanguageModel import ILargeLanguageModel


class GroqLLM(ILargeLanguageModel):
    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY must be set. "
                "Get a free key at https://console.groq.com"
            )
        
        self._client = Groq(api_key=api_key)
        
        # Default to fast Llama model (extremely fast inference)
        # Options: llama-3.3-70b-versatile, llama-3.1-70b-versatile, 
        #          mixtral-8x7b-32768, gemma2-9b-it
        self._model_name = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        print(f"[GroqLLM] Initialized with model: {self._model_name}")

    async def complete(self, system_prompt: str, user_message: str) -> str:
        """
        One-shot completion with JSON output.
        Used for grammar correction.
        """
        print(f"[GroqLLM] Generating completion (JSON mode)...")
        
        loop = asyncio.get_event_loop()
        
        def _sync_complete():
            response = self._client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content.strip()
        
        result = await loop.run_in_executor(None, _sync_complete)
        print(f"[GroqLLM] Completion result: '{result[:100]}...'")
        return result

    async def stream_complete(
        self, system_prompt: str, user_message: str
    ) -> AsyncGenerator[str, None]:
        """
        Streaming completion for conversational responses.
        Used for NPC dialogue generation.
        
        Groq is EXTREMELY fast - streaming gives sub-second first token.
        """
        print(f"[GroqLLM] Starting streaming generation...")
        
        loop = asyncio.get_event_loop()
        
        # Create iterator in executor to avoid blocking
        def _create_stream():
            return self._client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.8,
                stream=True
            )
        
        stream = await loop.run_in_executor(None, _create_stream)
        
        chunk_count = 0
        # Wrap synchronous iterator to yield control to event loop
        # This prevents blocking while TTS is generating audio
        for chunk in stream:
            if chunk.choices[0].delta.content:
                chunk_count += 1
                text = chunk.choices[0].delta.content
                if chunk_count <= 3 or chunk_count % 10 == 0:
                    print(f"[GroqLLM] Chunk #{chunk_count}: '{text[:30]}...'")
                yield text
                # Yield control to event loop after each chunk
                # This allows TTS to process sentences concurrently
                await asyncio.sleep(0)
        
        print(f"[GroqLLM] Stream complete. Total chunks: {chunk_count}")
