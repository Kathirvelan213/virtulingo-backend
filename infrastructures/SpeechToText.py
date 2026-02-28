"""
Whisper (Faster-Whisper) Implementation of ISpeechToText.

Runs fully locally (no API keys required).
Uses faster-whisper for improved speed.
"""

import io
import asyncio
from typing import AsyncGenerator

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

from domain.interfaces.ISpeechToText import ISpeechToText


class WhisperSTT(ISpeechToText):
    def __init__(self):
        # Model sizes: tiny, base, small, medium, large-v3
        # For dev: "small" is good balance
        self._model = WhisperModel(
            "small",
            device="cpu",       # change to "cuda" if GPU available
            compute_type="int8" # faster CPU inference
        )

    def _transcribe_sync(self, audio_bytes: bytes, language: str) -> str:
        # Convert raw bytes to numpy audio
        audio_buffer = io.BytesIO(audio_bytes)
        audio, sr = sf.read(audio_buffer)

        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        segments, _ = self._model.transcribe(
            audio,
            language=language,
            beam_size=5
        )

        transcript = " ".join([segment.text for segment in segments])
        return transcript.strip()

    async def transcribe(self, audio_bytes: bytes, language: str = "fr") -> str:
        """
        Transcribe complete audio buffer.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._transcribe_sync, audio_bytes, language
        )

    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: str = "fr"
    ) -> AsyncGenerator[str, None]:
        """
        Simulated streaming transcription.
        Buffers audio until pause threshold and transcribes.
        """

        buffer = bytearray()

        async for chunk in audio_stream:
            buffer.extend(chunk)

            # simple threshold flush (~1 second of audio)
            if len(buffer) > 32000:
                transcript = await self.transcribe(bytes(buffer), language)
                if transcript:
                    yield transcript
                buffer.clear()

        # flush remaining
        if buffer:
            transcript = await self.transcribe(bytes(buffer), language)
            if transcript:
                yield transcript