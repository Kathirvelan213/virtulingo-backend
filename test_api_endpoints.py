"""
HTTP/WebSocket Endpoint Test Script

Tests the actual FastAPI endpoints (WebSocket) to validate the full STT → LLM → TTS flow.
This simulates a Unity client connecting to the backend.

Prerequisites:
1. Backend server running: uvicorn main:app --reload
2. Ollama running: ollama serve
3. Model pulled: ollama pull llama3

Usage:
    python test_api_endpoints.py --mock      # Use mock audio (no real STT)
    python test_api_endpoints.py --real      # Use real audio file (requires audio.wav)
"""
import asyncio
import json
import argparse
from pathlib import Path
import websockets
import wave
import io


def create_mock_wav(duration_seconds=1, sample_rate=16000):
    """
    Create a valid WAV file with silence.
    Returns bytes that can be sent to the STT service.
    """
    num_samples = duration_seconds * sample_rate
    
    # Create WAV file in memory
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b'\x00\x00' * num_samples)  # Silence
    
    return buffer.getvalue()


# Mock audio data (valid WAV format)
MOCK_AUDIO = create_mock_wav()


async def test_conversation_endpoint(use_real_audio: bool = False):
    """
    Test the /ws/{player_id}/{npc_id} WebSocket endpoint.
    
    Protocol:
    1. Connect to WebSocket
    2. Send audio bytes (binary frames)
    3. Send end_utterance signal (JSON text frame)
    4. Receive:
       - Audio chunks (binary frames) for NPC voice
       - Events (JSON text frames) for grammar corrections
       - turn_complete signal
    """
    print("\n" + "="*80)
    print("Testing Conversation WebSocket Endpoint")
    print("="*80)
    
    player_id = "test_player_123"
    npc_id = "test_npc_456"
    ws_url = f"ws://localhost:8000/api/conversations/ws/{player_id}/{npc_id}"
    
    print(f"\n[WebSocket] Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ Connected successfully!")
            
            # Step 1: Send audio data
            if use_real_audio:
                audio_path = Path("test_audio.wav")
                if not audio_path.exists():
                    print("❌ test_audio.wav not found. Using mock audio instead.")
                    audio_data = MOCK_AUDIO
                else:
                    print(f"\n[Audio] Loading from {audio_path}")
                    audio_data = audio_path.read_bytes()
            else:
                print("\n[Audio] Using mock audio data (1 second of silence)")
                audio_data = MOCK_AUDIO
            
            # Send audio in chunks (simulate streaming)
            chunk_size = 4096
            total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size
            
            print(f"[Audio] Sending {len(audio_data)} bytes in {total_chunks} chunks...")
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                await websocket.send(chunk)
                print(f"  └─ Chunk {i//chunk_size + 1}/{total_chunks} sent ({len(chunk)} bytes)")
            
            print("\n[Signal] Sending end_utterance signal...")
            await websocket.send(json.dumps({"type": "end_utterance"}))
            
            # Step 2: Receive responses
            print("\n[Response] Waiting for NPC response...")
            audio_chunks_received = 0
            events_received = []
            transcription_text = None
            npc_reply_text = []
            grammar_corrections = []
            
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    
                    # Binary frame = audio chunk
                    if isinstance(message, bytes):
                        audio_chunks_received += 1
                        print(f"  🔊 Audio chunk #{audio_chunks_received} received ({len(message)} bytes)")
                    
                    # Text frame = event or signal
                    elif isinstance(message, str):
                        data = json.loads(message)
                        msg_type = data.get("type")
                        
                        if msg_type == "turn_complete":
                            print("\n✅ Turn complete signal received!")
                            break
                        
                        elif msg_type == "grammar_correction":
                            events_received.append(data)
                            correction_data = data.get('data', {})
                            grammar_corrections.append(correction_data)
                            print(f"\n  📝 Grammar correction event:")
                            print(f"      Original: {correction_data.get('original_text', 'N/A')}")
                            print(f"      Corrected: {correction_data.get('corrected_text', 'N/A')}")
                        
                        elif msg_type == "transcription":
                            transcription_text = data.get('text', 'N/A')
                            print(f"\n  📄 Transcription: {transcription_text}")
                        
                        elif msg_type == "npc_text":
                            # NPC text chunk (if backend sends it)
                            text_chunk = data.get('text', '')
                            npc_reply_text.append(text_chunk)
                            print(f"  💬 NPC text chunk: {text_chunk}")
                        
                        elif msg_type == "error":
                            print(f"\n❌ Server error: {data.get('message', 'Unknown error')}")
                            break
                        
                        else:
                            print(f"\n  📬 Event: {data}")
                
                except asyncio.TimeoutError:
                    print("\n⚠️  Timeout waiting for response")
                    break
            
            # Summary
            print("\n" + "="*80)
            print("CONVERSATION SUMMARY")
            print("="*80)
            
            print("\n📝 TRANSCRIPTION (STT Output):")
            print(f"   {transcription_text if transcription_text else 'N/A'}")
            
            if grammar_corrections:
                print("\n✏️  GRAMMAR CORRECTIONS:")
                for i, correction in enumerate(grammar_corrections, 1):
                    print(f"   {i}. Original:  {correction.get('original_text', 'N/A')}")
                    print(f"      Corrected: {correction.get('corrected_text', 'N/A')}")
                    if correction.get('mistakes'):
                        print(f"      Mistakes: {', '.join(m.get('type', 'unknown') for m in correction['mistakes'])}")
            
            if npc_reply_text:
                print("\n💬 NPC REPLY (LLM Output):")
                full_reply = ''.join(npc_reply_text)
                print(f"   {full_reply}")
            
            print("\n" + "-"*80)
            print("Technical Stats:")
            print(f"  ✓ Audio chunks received: {audio_chunks_received}")
            print(f"  ✓ Events received: {len(events_received)}")
            print("-"*80)
            
            if audio_chunks_received > 0:
                print("\n✅ TEST PASSED: Full workflow completed successfully!")
            else:
                print("\n❌ TEST FAILED: No audio chunks received from NPC")
    
    except websockets.exceptions.WebSocketException as e:
        print(f"\n❌ WebSocket error: {e}")
        print("\n💡 Make sure the backend server is running:")
        print("   uvicorn main:app --reload")
    
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


async def test_health_check():
    """
    Verify Ollama is running and model is available.
    """
    print("\n" + "="*80)
    print("Health Check: Ollama")
    print("="*80)
    
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            # Check Ollama is running
            print("\n[Ollama] Checking if Ollama is running...")
            response = await client.get("http://localhost:11434/api/tags")
            
            if response.status_code == 200:
                print("✅ Ollama is running")
                
                # Check if llama3 model is available
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                print(f"\n[Ollama] Available models: {models}")
                
                if any("llama3" in m for m in models):
                    print("✅ llama3 model is available")
                else:
                    print("⚠️  llama3 model not found")
                    print("   Run: ollama pull llama3")
            else:
                print(f"❌ Ollama returned status {response.status_code}")
    
    except httpx.ConnectError:
        print("❌ Cannot connect to Ollama")
        print("   Make sure Ollama is running: ollama serve")
    
    except Exception as e:
        print(f"❌ Health check failed: {e}")


async def test_backend_health():
    """
    Verify FastAPI backend is running.
    """
    print("\n" + "="*80)
    print("Health Check: Backend Server")
    print("="*80)
    
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            print("\n[Backend] Checking if FastAPI server is running...")
            response = await client.get("http://localhost:8000/docs")
            
            if response.status_code == 200:
                print("✅ FastAPI backend is running")
                print("   API docs: http://localhost:8000/docs")
            else:
                print(f"❌ Backend returned status {response.status_code}")
    
    except httpx.ConnectError:
        print("❌ Cannot connect to backend")
        print("   Start the server: uvicorn main:app --reload")
    
    except Exception as e:
        print(f"❌ Health check failed: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Test FastAPI WebSocket endpoints")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock audio data (default)"
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use real audio file (test_audio.wav)"
    )
    parser.add_argument(
        "--skip-health",
        action="store_true",
        help="Skip health checks"
    )
    
    args = parser.parse_args()
    use_real = args.real
    
    print("\n🧪 Virtulingo Backend - API Endpoint Test")
    print("="*80)
    
    # Health checks
    if not args.skip_health:
        await test_backend_health()
        await test_health_check()
    
    # Main test
    await test_conversation_endpoint(use_real_audio=use_real)
    
    print("\n" + "="*80)
    print("Test Complete")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
