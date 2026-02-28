from abc import ABC, abstractmethod
from typing import AsyncGenerator


class ITextToSpeech(ABC):
    """
    Interface for Text-to-Speech synthesis.
    """

    @abstractmethod
    async def synthesize(self, text: str, voice_id: str) -> bytes:
        """
        Synthesize the full text into an audio buffer.

        Args:
            text:     The text to speak.
            voice_id: Provider-specific voice/speaker identifier for this NPC.

        Returns:
            Raw audio bytes (typically MP3 or PCM).
        """
        ...

    @abstractmethod
    async def synthesize_stream(
        self, text_stream: AsyncGenerator[str, None], voice_id: str
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize a streaming text input into streaming audio chunks.
        Allows Unity to begin playback while generation continues.

        Args:
            text_stream: AsyncGenerator yielding text chunks from the LLM.
            voice_id:    Speaker voice identifier.

        Yields:
            Audio byte chunks.
        """
        ...
