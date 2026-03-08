"""
Azure Cognitive Services Text-to-Speech Implementation.

Uses Azure Speech SDK for high-quality neural voices.
Fast, reliable, and better quality than Google TTS.
"""

import os
import asyncio
import io
from typing import AsyncGenerator

import azure.cognitiveservices.speech as speechsdk

from domain.interfaces.ITextToSpeech import ITextToSpeech


class AzureTTS(ITextToSpeech):
    def __init__(self):
        """
        Initialize Azure Speech Service.
        
        Required env vars:
        - AZURE_SPEECH_KEY: Your Azure Speech service key
        - AZURE_SPEECH_REGION: Azure region (e.g., 'eastus', 'westus2')
        """
        speech_key = os.getenv('AZURE_SPEECH_KEY')
        speech_region = os.getenv('AZURE_SPEECH_REGION', 'eastus')
        
        if not speech_key:
            raise ValueError("AZURE_SPEECH_KEY must be set")
        
        # Speech config
        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key,
            region=speech_region
        )
        
        # Use neural voice (high quality, natural sounding)
        # Female: en-US-AriaNeural, en-US-JennyNeural
        # Male: en-US-GuyNeural, en-US-DavisNeural
        self.speech_config.speech_synthesis_voice_name = os.getenv(
            'AZURE_TTS_VOICE', 
            'en-US-AriaNeural'
        )
        
        # Output format: 16kHz WAV for Unity (RIFF = WAV container with headers)
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
        )
        
        print(f"[AzureTTS] Initialized with voice: {self.speech_config.speech_synthesis_voice_name}")

    def _generate_audio_bytes(self, text: str, voice_id: str = None) -> bytes:
        """
        Synchronous TTS generation.
        
        Args:
            text: Text to synthesize
            voice_id: Optional voice override (e.g., 'en-US-GuyNeural' for male)
        
        Returns:
            WAV audio bytes (16kHz mono with RIFF headers)
        """
        print(f"[AzureTTS] Generating audio for text (len={len(text)}): '{text[:100]}...'")
        print(f"[AzureTTS] Using voice: {voice_id or self.speech_config.speech_synthesis_voice_name}")
        
        # Create a one-time synthesizer
        if voice_id:
            # Override voice temporarily
            config = speechsdk.SpeechConfig(
                subscription=self.speech_config.subscription_key,
                region=self.speech_config.region
            )
            config.speech_synthesis_voice_name = voice_id
            config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
            )
        else:
            config = self.speech_config
        
        # Synthesize to memory stream
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=config,
            audio_config=None  # None = return audio data
        )
        
        result = synthesizer.speak_text(text)
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print(f"[AzureTTS] Successfully generated {len(result.audio_data)} bytes")
            return result.audio_data
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            error_msg = f"Azure TTS failed: {cancellation.reason} - {cancellation.error_details}"
            print(f"[AzureTTS] ERROR: {error_msg}")
            raise Exception(error_msg)
        else:
            error_msg = f"Azure TTS failed with reason: {result.reason}"
            print(f"[AzureTTS] ERROR: {error_msg}")
            raise Exception(error_msg)

    async def synthesize(self, text: str, voice_id: str = None) -> bytes:
        """
        One-shot synthesis - returns complete audio bytes.
        
        Args:
            text: Text to synthesize
            voice_id: Optional voice ID override
        
        Returns:
            WAV audio bytes (16kHz, 16-bit, mono)
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
        sentence_count = 0

        async for chunk in text_stream:
            buffer_parts.append(chunk)
            assembled = "".join(buffer_parts)

            # Yield at sentence boundaries for faster playback
            if any(assembled.endswith(p) for p in (".", "!", "?")):
                sentence_count += 1
                print(f"[AzureTTS] Synthesizing sentence #{sentence_count}: '{assembled[:50]}...'")
                audio_bytes = await self.synthesize(assembled, voice_id)
                print(f"[AzureTTS] Generated {len(audio_bytes)} bytes for sentence #{sentence_count}")
                yield audio_bytes
                buffer_parts = []

        # Flush remainder
        remainder = "".join(buffer_parts).strip()
        if remainder:
            sentence_count += 1
            print(f"[AzureTTS] Synthesizing final chunk: '{remainder[:50]}...'")
            audio_bytes = await self.synthesize(remainder, voice_id)
            print(f"[AzureTTS] Generated {len(audio_bytes)} bytes for final chunk")
            yield audio_bytes
        
        print(f"[AzureTTS] Stream complete. Total sentences: {sentence_count}")
