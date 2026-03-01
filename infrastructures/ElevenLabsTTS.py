"""
ElevenLabs Text-to-Speech Implementation with Streaming Support.

ElevenLabs provides high-quality, natural-sounding voices with streaming
capability, ideal for real-time conversational experiences.

Features:
- Streaming TTS: Start playing audio while text is still being generated
- One-shot TTS: Generate complete audio file
- Multiple voice options with emotion control
- Multilingual support

Requires: ELEVENLABS_API_KEY in environment variables
"""
import os
import json
import asyncio
from typing import AsyncGenerator, Optional

import httpx

from domain.interfaces.ITextToSpeech import ITextToSpeech


class ElevenLabsTTS(ITextToSpeech):
    """
    Production-grade streaming TTS using ElevenLabs.
    
    Supports two modes:
    1. Streaming: Generate audio chunks as text arrives (minimize latency)
    2. One-shot: Generate complete audio file from full text
    """
    
    def __init__(self):
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable is required")
        
        self._api_key = api_key
        self._base_url = "https://api.elevenlabs.io/v1"
        
        # Default settings
        self._model_id = "eleven_turbo_v2_5"  # Fast, low-latency model
        self._default_voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel (multilingual)
    
    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> bytes:
        """
        One-shot synthesis: generate complete audio file.
        
        Args:
            text: Text to synthesize
            voice_id: ElevenLabs voice ID (uses default if not provided)
        
        Returns:
            Complete audio data as MP3 bytes
        """
        voice_id = voice_id or self._default_voice_id
        
        url = f"{self._base_url}/text-to-speech/{voice_id}"
        
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        
        payload = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.content

    async def synthesize_stream(
        self,
        text_stream: AsyncGenerator[str, None],
        voice_id: Optional[str] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Streaming synthesis: generate audio as text chunks arrive.
        
        This implements sentence-boundary buffering:
        - Buffers text until a sentence boundary (. ! ? ; ,)
        - Generates audio for complete sentences
        - Yields audio chunks immediately
        
        This minimizes latency while maintaining natural speech rhythm.
        
        Args:
            text_stream: Async generator yielding text chunks from LLM
            voice_id: ElevenLabs voice ID
        
        Yields:
            Audio chunks (MP3 bytes) as they're generated
        """
        voice_id = voice_id or self._default_voice_id
        
        buffer_parts = []
        sentence_boundaries = (".", "!", "?", "\n")
        flush_boundaries = (",", ";")
        
        async for chunk in text_stream:
            buffer_parts.append(chunk)
            assembled = "".join(buffer_parts)
            
            # Check for sentence boundary
            should_flush = False
            
            for boundary in sentence_boundaries:
                if assembled.endswith(boundary):
                    should_flush = True
                    break
            
            # Also flush on commas/semicolons if buffer is long enough (for natural pauses)
            if not should_flush and len(assembled) > 100:
                for boundary in flush_boundaries:
                    if assembled.endswith(boundary):
                        should_flush = True
                        break
            
            if should_flush:
                audio_chunk = await self.synthesize(assembled, voice_id)
                yield audio_chunk
                buffer_parts = []
        
        # Flush any remaining text
        remainder = "".join(buffer_parts).strip()
        if remainder:
            audio_chunk = await self.synthesize(remainder, voice_id)
            yield audio_chunk

    async def synthesize_stream_websocket(
        self,
        text_stream: AsyncGenerator[str, None],
        voice_id: Optional[str] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        True streaming using ElevenLabs WebSocket API.
        
        This uses ElevenLabs' native streaming endpoint for ultra-low latency.
        Audio chunks are generated and streamed as text tokens arrive.
        
        Args:
            text_stream: Async generator yielding text chunks
            voice_id: ElevenLabs voice ID
        
        Yields:
            Audio chunks (MP3 bytes) in real-time
        """
        voice_id = voice_id or self._default_voice_id
        
        # WebSocket streaming endpoint
        ws_url = f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input?model_id={self._model_id}"
        
        import websockets
        
        async with websockets.connect(
            ws_url,
            extra_headers={"xi-api-key": self._api_key}
        ) as websocket:
            
            # Send initial configuration
            await websocket.send(json.dumps({
                "text": " ",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
                "xi_api_key": self._api_key,
            }))
            
            # Create task to send text chunks
            async def send_text():
                try:
                    async for text_chunk in text_stream:
                        await websocket.send(json.dumps({
                            "text": text_chunk,
                            "try_trigger_generation": True,
                        }))
                    
                    # Signal end of text stream
                    await websocket.send(json.dumps({"text": ""}))
                
                except Exception as e:
                    print(f"[ElevenLabsTTS] Error sending text: {e}")
            
            send_task = asyncio.create_task(send_text())
            
            # Receive and yield audio chunks
            try:
                while True:
                    response = await websocket.recv()
                    
                    if isinstance(response, bytes):
                        # Audio chunk
                        yield response
                    else:
                        # JSON message
                        data = json.loads(response)
                        
                        if data.get("audio"):
                            # Base64-encoded audio
                            import base64
                            audio_bytes = base64.b64decode(data["audio"])
                            yield audio_bytes
                        
                        if data.get("isFinal"):
                            break
            
            finally:
                await send_task


class ElevenLabsTTSConfigurable(ElevenLabsTTS):
    """
    Extended version with configurable voice settings.
    Use this for fine-tuned emotion and style control.
    """
    
    def __init__(
        self,
        model_id: str = "eleven_turbo_v2_5",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        use_speaker_boost: bool = True,
    ):
        super().__init__()
        self._model_id = model_id
        self._voice_settings = {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": use_speaker_boost,
        }
    
    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> bytes:
        """Synthesis with custom voice settings."""
        voice_id = voice_id or self._default_voice_id
        
        url = f"{self._base_url}/text-to-speech/{voice_id}"
        
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        
        payload = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": self._voice_settings,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.content

