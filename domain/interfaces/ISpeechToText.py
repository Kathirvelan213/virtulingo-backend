from abc import ABC, abstractmethod
from typing import AsyncGenerator


class ISpeechToText(ABC):
    """
    Interface for Speech-to-Text transcription.
    Implementations must support both streaming and one-shot transcription.
    """

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language: str = "fr") -> str:
        """
        Transcribe a complete audio buffer to text.

        Args:
            audio_bytes: Raw PCM or encoded audio bytes.
            language:    BCP-47 language code of the target language being spoken.

        Returns:
            Transcribed text string.
        """
        ...

    @abstractmethod
    async def transcribe_stream(
        self, audio_stream: AsyncGenerator[bytes, None], language: str = "fr"
    ) -> AsyncGenerator[str, None]:
        """
        Transcribe a live audio stream, yielding partial text chunks as they arrive.

        Args:
            audio_stream: AsyncGenerator producing audio byte chunks.
            language:     BCP-47 language code.

        Yields:
            Partial transcription strings.
        """
        ...
