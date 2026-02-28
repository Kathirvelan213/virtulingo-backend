"""
Coqui TTS Implementation of ITextToSpeech.

Runs fully locally (no API keys required).
Generates WAV audio bytes for Unity playback.
"""

import io
import asyncio
from typing import AsyncGenerator

import numpy as np
import soundfile as sf
from TTS.api import TTS

from domain.interfaces.ITextToSpeech import ITextToSpeech


class CoquiTTS(ITextToSpeech):
    def __init__(self):
        # You can change model if needed
        self._model_name = "tts_models/en/ljspeech/tacotron2-DDC"
        self._tts = TTS(self._model_name)
        self._sample_rate = 22050

    def _generate_wav_bytes(self, text: str) -> bytes:
        """
        Generates WAV bytes from text.
        """
        wav = self._tts.tts(text)

        # Convert to numpy array
        wav = np.array(wav)

        # Write to in-memory buffer
        buffer = io.BytesIO()
        sf.write(buffer, wav, self._sample_rate, format="WAV")
        buffer.seek(0)

        return buffer.read()

    async def synthesize(self, text: str, voice_id: str = None) -> bytes:
        """
        One-shot synthesis — returns complete WAV audio bytes.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._generate_wav_bytes, text)

    async def synthesize_stream(
        self, text_stream: AsyncGenerator[str, None], voice_id: str = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Simulated streaming:
        Buffers text until sentence boundary, generates WAV, yields bytes.
        """
        buffer_parts = []

        async for chunk in text_stream:
            buffer_parts.append(chunk)
            assembled = "".join(buffer_parts)

            if any(assembled.endswith(p) for p in (".", "!", "?", ",", ";")):
                wav_bytes = await self.synthesize(assembled)
                yield wav_bytes
                buffer_parts = []

        # Flush remainder
        remainder = "".join(buffer_parts).strip()
        if remainder:
            wav_bytes = await self.synthesize(remainder)
            yield wav_bytes