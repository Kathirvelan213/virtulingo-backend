"""
Test Script for VirtuLingo STT → Grammar + LLM → TTS Workflow

This script tests the complete conversation pipeline:
1. Speech-to-Text (Whisper)
2. Parallel: Grammar Correction (LLM) + Conversation (LLM)
3. Text-to-Speech (Coqui TTS)

Usage:
    # Test with mocked services (fast, no API keys needed):
    python test_workflow.py --mock

    # Test with real services (requires GOOGLE_API_KEY for Gemini):
    python test_workflow.py --real

    # Test specific components:
    python test_workflow.py --stt-only
    python test_workflow.py --llm-only
    python test_workflow.py --tts-only
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()


# ============================================================================
# Mock Implementations for Testing
# ============================================================================

class MockSTT:
    """Mock STT for testing without Whisper dependencies."""
    
    async def transcribe(self, audio_bytes: bytes, language: str = "fr") -> str:
        print("  [MockSTT] Transcribing audio...")
        await asyncio.sleep(0.5)  # Simulate processing time
        return "Bonjour, je voudrais acheter du pain s'il vous plaît"
    
    async def transcribe_stream(
        self, audio_stream: AsyncGenerator[bytes, None], language: str = "fr"
    ) -> AsyncGenerator[str, None]:
        print("  [MockSTT] Streaming transcription...")
        async for chunk in audio_stream:
            await asyncio.sleep(0.2)
        yield "Bonjour, je voudrais acheter du pain s'il vous plaît"


class MockTTS:
    """Mock TTS for testing without Coqui dependencies."""
    
    async def synthesize(self, text: str, voice_id: str = None) -> bytes:
        print(f"  [MockTTS] Synthesizing: '{text[:50]}...'")
        await asyncio.sleep(0.3)
        return b"MOCK_AUDIO_DATA"
    
    async def synthesize_stream(
        self, text_stream: AsyncGenerator[str, None], voice_id: str = None
    ) -> AsyncGenerator[bytes, None]:
        print("  [MockTTS] Streaming synthesis...")
        buffer = []
        async for chunk in text_stream:
            buffer.append(chunk)
            if any(chunk.endswith(p) for p in (".", "!", "?", "\n")):
                text = "".join(buffer)
                print(f"  [MockTTS] → Audio chunk for: '{text[:40]}...'")
                yield b"MOCK_AUDIO_CHUNK"
                buffer = []
        
        if buffer:
            yield b"MOCK_AUDIO_CHUNK_FINAL"


class MockLLM:
    """Mock LLM for testing without LLM API."""
    
    async def complete(self, system_prompt: str, user_message: str) -> str:
        print("  [MockLLM] Grammar analysis...")
        await asyncio.sleep(0.4)
        
        # Simulate grammar correction response
        return json.dumps({
            "mistake_found": True,
            "category": "verb_conjugation",
            "original": "je voudrais",
            "correction": "je voudrais (correct)",
            "explanation": "Conditional form is correct for polite requests",
            "severity": 1
        })
    
    async def stream_complete(
        self, system_prompt: str, user_message: str
    ) -> AsyncGenerator[str, None]:
        print("  [MockLLM] Streaming NPC response...")
        
        # Simulate streaming response from NPC
        response_parts = [
            "Bien sûr! ",
            "Nous avons du pain ",
            "frais aujourd'hui. ",
            "Quel type de pain ",
            "voulez-vous?"
        ]
        
        for part in response_parts:
            await asyncio.sleep(0.2)
            yield part


class MockWorldStateRepo:
    """Mock world state repository."""
    
    async def get_player_state(self, player_id: str) -> dict:
        return {
            "language": "fr",
            "proficiency_level": "A2",
            "scene_id": "bakery",
            "object_in_hand": None,
            "active_quest": "buy_bread",
        }
    
    async def append_conversation_turn(
        self, player_id: str, npc_id: str, role: str, content: str
    ):
        print(f"  [WorldState] Logged {role}: '{content[:50]}...'")
    
    async def get_conversation_history(
        self, player_id: str, npc_id: str, window: int = 10
    ) -> list:
        return [
            {"role": "player", "content": "Bonjour!"},
            {"role": "npc", "content": "Bonjour! Comment puis-je vous aider?"},
        ]


class MockMistakeRepo:
    """Mock mistake repository."""
    
    def __init__(self):
        self.mistakes = []
    
    async def log_mistake(
        self, player_id: str, category: str, original: str, 
        correction: str, explanation: str
    ):
        self.mistakes.append({
            "player_id": player_id,
            "category": category,
            "original": original,
            "correction": correction,
            "explanation": explanation,
        })
        print(f"  [MistakeRepo] Logged mistake: {category}")


class MockNPCRepo:
    """Mock NPC repository."""
    
    async def get_npc_profile(self, npc_id: str) -> dict:
        return {
            "npc_id": npc_id,
            "name": "Marie",
            "personality": "friendly baker",
            "backstory": "Marie has owned this bakery for 20 years",
            "language_complexity": "B1",
            "emotional_tone": "warm and welcoming",
            "voice_id": "marie_voice",
            "relationship_score": 0.5,
        }


class MockPlayerProfileRepo:
    """Mock player profile repository."""
    
    async def get_profile(self, player_id: str) -> dict:
        return {
            "player_id": player_id,
            "proficiency_level": "A2",
            "native_language": "en",
            "target_language": "fr",
        }


# ============================================================================
# Test Functions
# ============================================================================

async def test_stt_only(use_real: bool = False):
    """Test Speech-to-Text in isolation."""
    print("\n" + "="*70)
    print("TEST: Speech-to-Text Only")
    print("="*70)
    
    if use_real:
        from infrastructures.SpeechToText import WhisperSTT
        stt = WhisperSTT()
        
        # Generate some test audio (silence)
        import numpy as np
        import soundfile as sf
        import io
        
        # Create 2 seconds of silence at 16kHz
        sample_rate = 16000
        duration = 2
        audio = np.zeros(sample_rate * duration, dtype=np.float32)
        
        buffer = io.BytesIO()
        sf.write(buffer, audio, sample_rate, format='WAV')
        audio_bytes = buffer.getvalue()
        
        print("\n📢 Testing with real Whisper STT...")
        result = await stt.transcribe(audio_bytes, language="fr")
        print(f"✅ Transcription: '{result}'")
    else:
        stt = MockSTT()
        print("\n📢 Testing with mock STT...")
        result = await stt.transcribe(b"MOCK_AUDIO", language="fr")
        print(f"✅ Transcription: '{result}'")


async def test_llm_only(use_real: bool = False):
    """Test LLM in isolation."""
    print("\n" + "="*70)
    print("TEST: LLM Only (Grammar + Conversation)")
    print("="*70)
    
    if use_real:
        from infrastructures.GeminiLLM import GeminiLLM
        llm = GeminiLLM()
        print("\n🤖 Testing with real Gemini LLM...")
    else:
        llm = MockLLM()
        print("\n🤖 Testing with mock LLM...")
    
    # Test grammar correction
    print("\n1️⃣ Grammar Correction Test:")
    grammar_prompt = """
    You are an expert French language teacher.
    Return ONLY valid JSON with this schema:
    {"mistake_found": bool, "category": str, "original": str, "correction": str, "explanation": str, "severity": int}
    """
    
    result = await llm.complete(grammar_prompt, "Je vais au marché hier")
    print(f"✅ Grammar Result: {result}")
    
    # Test conversation streaming
    print("\n2️⃣ Conversation Streaming Test:")
    conv_prompt = "You are Marie, a friendly French baker. Respond in French."
    
    print("Streaming chunks:")
    chunks = []
    async for chunk in llm.stream_complete(conv_prompt, "Bonjour, je voudrais du pain"):
        print(f"  → '{chunk}'", end="", flush=True)
        chunks.append(chunk)
    
    print(f"\n✅ Complete response: '{''.join(chunks)}'")


async def test_tts_only(use_real: bool = False):
    """Test Text-to-Speech in isolation."""
    print("\n" + "="*70)
    print("TEST: Text-to-Speech Only")
    print("="*70)
    
    if use_real:
        from infrastructures.TextToSpeech import CoquiTTS
        tts = CoquiTTS()
        print("\n🔊 Testing with real Coqui TTS...")
    else:
        tts = MockTTS()
        print("\n🔊 Testing with mock TTS...")
    
    # Test one-shot synthesis
    print("\n1️⃣ One-shot synthesis:")
    text = "Bonjour! Comment allez-vous aujourd'hui?"
    audio = await tts.synthesize(text)
    print(f"✅ Generated {len(audio)} bytes of audio")
    
    # Test streaming synthesis
    print("\n2️⃣ Streaming synthesis:")
    
    async def text_generator():
        parts = ["Bonjour! ", "Comment allez-vous? ", "Ça va bien?"]
        for part in parts:
            await asyncio.sleep(0.1)
            yield part
    
    total_bytes = 0
    async for audio_chunk in tts.synthesize_stream(text_generator()):
        total_bytes += len(audio_chunk)
        print(f"  → Received {len(audio_chunk)} bytes")
    
    print(f"✅ Total audio: {total_bytes} bytes")


async def test_full_workflow(use_real: bool = False):
    """Test the complete STT → Grammar + LLM → TTS workflow."""
    print("\n" + "="*70)
    print("TEST: Full Conversation Workflow")
    print("="*70)
    
    # Initialize services
    if use_real:
        print("\n⚙️  Initializing REAL services (requires GOOGLE_API_KEY)...")
        from infrastructures.GeminiLLM import GeminiLLM
        from infrastructures.SpeechToText import WhisperSTT
        from infrastructures.TextToSpeech import CoquiTTS
        
        llm = GeminiLLM()
        stt = WhisperSTT()
        tts = CoquiTTS()
        
        # For audio, use mock (you'd need actual audio file)
        import numpy as np
        import soundfile as sf
        import io
        sample_rate = 16000
        duration = 2
        audio = np.zeros(sample_rate * duration, dtype=np.float32)
        buffer = io.BytesIO()
        sf.write(buffer, audio, sample_rate, format='WAV')
        audio_bytes = buffer.getvalue()
    else:
        print("\n⚙️  Initializing MOCK services (fast testing)...")
        llm = MockLLM()
        stt = MockSTT()
        tts = MockTTS()
        audio_bytes = b"MOCK_AUDIO_DATA"
    
    # Initialize repositories
    world_state_repo = MockWorldStateRepo()
    mistake_repo = MockMistakeRepo()
    npc_repo = MockNPCRepo()
    player_profile_repo = MockPlayerProfileRepo()
    
    # Event callback to track events
    events_received = []
    
    async def event_callback(event: dict):
        events_received.append(event)
        print(f"\n  📨 Event: {event.get('type')} - {event.get('data', {}).get('category', 'N/A')}")
    
    # Import and initialize DialogueOrchestrator
    from application.DialogueOrchestrator import DialogueOrchestrator
    
    orchestrator = DialogueOrchestrator(
        world_state_repo=world_state_repo,
        mistake_repo=mistake_repo,
        npc_repo=npc_repo,
        player_profile_repo=player_profile_repo,
        stt_service=stt,
        tts_service=tts,
        llm_service=llm,
        event_callback=event_callback,
    )
    
    # Run the complete workflow
    print("\n🎬 Starting conversation workflow...")
    print("="*70)
    
    player_id = "test_player_123"
    npc_id = "npc_baker_marie"
    
    print("\n📝 STEP 1: Player speaks (audio input)")
    print(f"  Audio size: {len(audio_bytes)} bytes")
    
    audio_chunks = []
    chunk_count = 0
    
    print("\n🔄 STEP 2-4: Processing (STT → Grammar + LLM → TTS)")
    async for audio_chunk in orchestrator.process_conversation_turn(
        player_id=player_id,
        npc_id=npc_id,
        audio_bytes=audio_bytes,
    ):
        chunk_count += 1
        audio_chunks.append(audio_chunk)
        print(f"  📦 Received audio chunk #{chunk_count} ({len(audio_chunk)} bytes)")
    
    print("\n" + "="*70)
    print("✅ WORKFLOW COMPLETED")
    print("="*70)
    print(f"\n📊 Results:")
    print(f"  • Total audio chunks received: {chunk_count}")
    print(f"  • Total audio bytes: {sum(len(c) for c in audio_chunks)}")
    print(f"  • Grammar correction events: {len(events_received)}")
    print(f"  • Mistakes logged: {len(mistake_repo.mistakes)}")
    
    if mistake_repo.mistakes:
        print(f"\n🔍 Grammar Mistakes Detected:")
        for mistake in mistake_repo.mistakes:
            print(f"  • {mistake['category']}: '{mistake['original']}' → '{mistake['correction']}'")
            print(f"    Explanation: {mistake['explanation']}")
    
    if events_received:
        print(f"\n📨 Events Fired:")
        for event in events_received:
            print(f"  • {event.get('type')}: {json.dumps(event.get('data', {}), indent=4)}")


async def test_streaming_workflow(use_real: bool = False):
    """Test the streaming variant of the workflow."""
    print("\n" + "="*70)
    print("TEST: Streaming Conversation Workflow")
    print("="*70)
    
    # Similar to test_full_workflow but uses streaming
    print("\n⚙️  Initializing services...")
    
    if use_real:
        from infrastructures.GeminiLLM import GeminiLLM
        from infrastructures.SpeechToText import WhisperSTT
        from infrastructures.TextToSpeech import CoquiTTS
        
        llm = GeminiLLM()
        stt = WhisperSTT()
        tts = CoquiTTS()
    else:
        llm = MockLLM()
        stt = MockSTT()
        tts = MockTTS()
    
    world_state_repo = MockWorldStateRepo()
    mistake_repo = MockMistakeRepo()
    npc_repo = MockNPCRepo()
    player_profile_repo = MockPlayerProfileRepo()
    
    async def event_callback(event: dict):
        print(f"\n  📨 Event: {event.get('type')}")
    
    from application.DialogueOrchestrator import DialogueOrchestrator
    
    orchestrator = DialogueOrchestrator(
        world_state_repo=world_state_repo,
        mistake_repo=mistake_repo,
        npc_repo=npc_repo,
        player_profile_repo=player_profile_repo,
        stt_service=stt,
        tts_service=tts,
        llm_service=llm,
        event_callback=event_callback,
    )
    
    # Simulate streaming audio input
    async def audio_stream():
        print("  🎤 Streaming audio chunks...")
        for i in range(3):
            await asyncio.sleep(0.1)
            yield b"AUDIO_CHUNK_" + str(i).encode()
    
    print("\n🎬 Starting streaming workflow...")
    
    chunk_count = 0
    async for audio_chunk in orchestrator.process_streaming_conversation(
        player_id="test_player",
        npc_id="test_npc",
        audio_stream=audio_stream(),
    ):
        chunk_count += 1
        print(f"  📦 Audio chunk #{chunk_count}")
    
    print(f"\n✅ Streaming completed: {chunk_count} chunks")


# ============================================================================
# Main Test Runner
# ============================================================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test VirtuLingo conversation workflow")
    parser.add_argument("--mock", action="store_true", help="Use mock services (default)")
    parser.add_argument("--real", action="store_true", help="Use real services (requires API keys)")
    parser.add_argument("--stt-only", action="store_true", help="Test STT only")
    parser.add_argument("--llm-only", action="store_true", help="Test LLM only")
    parser.add_argument("--tts-only", action="store_true", help="Test TTS only")
    parser.add_argument("--streaming", action="store_true", help="Test streaming workflow")
    
    args = parser.parse_args()
    
    use_real = args.real
    
    if use_real:
        print("\n⚠️  REAL MODE: Using actual AI services")
        print("  • Requires: GOOGLE_API_KEY environment variable")
        print("  • Requires: Whisper and Coqui TTS installed")
        
        if not os.environ.get("GOOGLE_API_KEY"):
            print("\n❌ ERROR: GOOGLE_API_KEY not found in environment")
            print("  Set it in your .env file or export it:")
            print("  export GOOGLE_API_KEY=your-api-key-here")
            return
    else:
        print("\n🎭 MOCK MODE: Using mock services (fast, no API keys needed)")
    
    try:
        if args.stt_only:
            await test_stt_only(use_real)
        elif args.llm_only:
            await test_llm_only(use_real)
        elif args.tts_only:
            await test_tts_only(use_real)
        elif args.streaming:
            await test_streaming_workflow(use_real)
        else:
            # Run full workflow test
            await test_full_workflow(use_real)
        
        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED")
        print("="*70)
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
