"""
Google Cloud Text-to-Speech Implementation of ITextToSpeech.

Uses the same Google API key as Gemini via REST API.
Much faster than local Coqui TTS (~100-300ms per request).
"""

import io
import asyncio
from typing import AsyncGenerator
import httpx
import base64
import os

from domain.interfaces.ITextToSpeech import ITextToSpeech


class GoogleCloudTTS(ITextToSpeech):
    def __init__(self):
        """
        Initialize Google Cloud TTS using REST API with API key.
        Uses the same GOOGLE_API_KEY as Gemini.
        """
        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY must be set for Google Cloud TTS")
        
        self.base_url = "https://texttospeech.googleapis.com/v1/text:synthesize"

    def _generate_audio_bytes(self, text: str, voice_id: str = None) -> bytes:
        """
        Generates audio bytes from text using Google Cloud TTS REST API.
        
        Args:
            text: Text to synthesize
            voice_id: Optional voice override (e.g., "en-US-Neural2-M" for male)
        
        Returns:
            WAV audio bytes (LINEAR16 PCM)
        """
        # Default to natural female voice
        voice_name = voice_id or "en-US-Neural2-F"
        
        # Request payload
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": "en-US",
                "name": voice_name,
                "ssmlGender": "FEMALE"
            },
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "sampleRateHertz": 16000
            }
        }
        
        # Make synchronous request
        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}?key={self.api_key}",
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
        
        # Extract audio content (base64 encoded)
        audio_base64 = response.json()["audioContent"]
        audio_bytes = base64.b64decode(audio_base64)
        
        return audio_bytes

    async def synthesize(self, text: str, voice_id: str = None) -> bytes:
        """
        One-shot synthesis — returns complete audio bytes.
        
        Args:
            text: Text to synthesize
            voice_id: Optional voice ID (e.g., "en-US-Neural2-M")
        
        Returns:
            WAV audio bytes
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._generate_audio_bytes, text, voice_id)

    async def synthesize_stream(
        self, text_stream: AsyncGenerator[str, None], voice_id: str = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Streaming synthesis:
        Buffers text until sentence boundary, generates audio, yields bytes.
        
        This allows Unity to start playing audio before the full response is complete.
        """
        buffer_parts = []

        async for chunk in text_stream:
            buffer_parts.append(chunk)
            assembled = "".join(buffer_parts)

            # Yield at sentence boundaries for faster playback
            if any(assembled.endswith(p) for p in (".", "!", "?")):
                audio_bytes = await self.synthesize(assembled, voice_id)
                yield audio_bytes
                buffer_parts = []

        # Flush remainder
        remainder = "".join(buffer_parts).strip()
        if remainder:
            audio_bytes = await self.synthesize(remainder, voice_id)
            yield audio_bytes
