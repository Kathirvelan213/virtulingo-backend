"""
Azure Speech-to-Text Implementation.

Uses Azure Cognitive Services Speech SDK for STT.
Fast, accurate speech recognition with support for multiple languages.
"""

import os
import asyncio
from typing import AsyncGenerator

import azure.cognitiveservices.speech as speechsdk

from domain.interfaces.ISpeechToText import ISpeechToText


class AzureSTT(ISpeechToText):
    def __init__(self):
        """
        Initialize Azure Speech Service for STT.
        
        Required env vars:
        - AZURE_SPEECH_KEY: Your Azure Speech service key
        - AZURE_SPEECH_REGION: Azure region (e.g., 'centralindia', 'eastus')
        """
        speech_key = os.getenv('AZURE_SPEECH_KEY')
        speech_region = os.getenv('AZURE_SPEECH_REGION', 'eastus')
        
        if not speech_key:
            raise ValueError("AZURE_SPEECH_KEY must be set")
        
        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key,
            region=speech_region
        )
        
        # Audio format: Unity sends PCM16 @ 16kHz mono
        self.audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=16000,
            bits_per_sample=16,
            channels=1
        )
        
        print(f"[AzureSTT] Initialized with region: {speech_region}")

    def _transcribe_sync(self, audio_bytes: bytes, language: str) -> str:
        """
        Synchronous transcription of audio bytes.
        
        Args:
            audio_bytes: Raw PCM16 audio data from Unity
            language: BCP-47 language code (e.g., 'fr-FR', 'en-US')
        
        Returns:
            Transcribed text
        """
        # Set recognition language
        self.speech_config.speech_recognition_language = language
        
        # Create push stream for audio data
        push_stream = speechsdk.audio.PushAudioInputStream(self.audio_format)
        push_stream.write(audio_bytes)
        push_stream.close()
        
        # Create audio config from push stream
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
        
        # Create speech recognizer
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=audio_config
        )
        
        # Perform recognition
        result = speech_recognizer.recognize_once()
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text
        elif result.reason == speechsdk.ResultReason.NoMatch:
            print(f"[AzureSTT] No speech recognized: {result.no_match_details}")
            return ""
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            raise Exception(f"Azure STT failed: {cancellation.reason} - {cancellation.error_details}")
        else:
            raise Exception(f"Azure STT failed with reason: {result.reason}")

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        """
        Transcribe complete audio buffer.
        
        Args:
            audio_bytes: Raw PCM16 audio bytes from Unity
            language: Language code (defaults to 'en' for English)
        
        Returns:
            Transcribed text
        """
        # Convert simple language code to BCP-47 format
        if language == "fr":
            language = "fr-FR"
        elif language == "en":
            language = "en-US"
        elif language == "es":
            language = "es-ES"
        elif language == "de":
            language = "de-DE"
        # Otherwise assume it's already BCP-47 format
        
        print(f"[AzureSTT] Transcribing {len(audio_bytes)} bytes in {language}")
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._transcribe_sync, audio_bytes, language
        )
        
        print(f"[AzureSTT] Result: '{result}'")
        return result

    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: str = "en"
    ) -> AsyncGenerator[str, None]:
        """
        Streaming transcription (buffers and transcribes in chunks).
        
        For true streaming, would need to use continuous recognition,
        but for this use case, buffering works well.
        """
        buffer = bytearray()
        
        async for chunk in audio_stream:
            buffer.extend(chunk)
        
        if buffer:
            text = await self.transcribe(bytes(buffer), language)
            if text:
                yield text
