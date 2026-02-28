from abc import ABC, abstractmethod

class ISTTService(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe streaming audio to text."""
        pass

class ITTSService(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio bytes."""
        pass

class ILLMService(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str, context: dict) -> str:
        """Generate response given a player's context."""
        pass
