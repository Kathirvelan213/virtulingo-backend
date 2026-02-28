from abc import ABC, abstractmethod
from typing import AsyncGenerator


class ILargeLanguageModel(ABC):
    """
    Interface for LLM inference — both one-shot and streaming.
    """

    @abstractmethod
    async def complete(self, system_prompt: str, user_message: str) -> str:
        """
        One-shot completion for structured outputs (e.g., grammar correction).

        Args:
            system_prompt: Instructions / persona context.
            user_message:  The player's input or query.

        Returns:
            Complete response string.
        """
        ...

    @abstractmethod
    async def stream_complete(
        self, system_prompt: str, user_message: str
    ) -> AsyncGenerator[str, None]:
        """
        Streaming completion yielding text chunks for low-latency TTS piping.

        Args:
            system_prompt: Assembled context + NPC personality prompt.
            user_message:  Player's transcribed utterance.

        Yields:
            Text chunks as they are generated.
        """
        ...
