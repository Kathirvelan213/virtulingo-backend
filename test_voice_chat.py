"""
Voice Chat Test Script for VirtuLingo Backend

Records audio from your microphone, sends it to the backend via WebSocket,
and plays back the NPC's audio response.

Prerequisites:
1. Backend server running: uvicorn main:app --reload
2. Install dependencies: pip install sounddevice soundfile websockets numpy

Usage:
    python test_voice_chat.py
    
    Press ENTER to start recording, speak, then press ENTER again to stop.
    The script will send your audio to the backend and play the NPC response.
"""
import asyncio
import json
import sounddevice as sd
import soundfile as sf
import numpy as np
import websockets
from pathlib import Path
import io
import wave
import threading
import httpx


# Configuration
BACKEND_URL = "ws://localhost:8000/api/conversations/ws"
PLAYER_ID = "test_player_123"
NPC_ID = "test_npc_001"
SAMPLE_RATE = 16000  # 16kHz for speech
CHANNELS = 1  # Mono
TEMP_INPUT_FILE = "temp_input.wav"
TEMP_OUTPUT_FILE = "temp_output.wav"


class AudioRecorder:
    """Handles microphone recording with manual start/stop."""
    
    def __init__(self, sample_rate=SAMPLE_RATE, channels=CHANNELS):
        self.sample_rate = sample_rate
        self.channels = channels
        self.recording = []
        self.is_recording = False
        
    def start(self):
        """Start recording audio."""
        self.recording = []
        self.is_recording = True
        print("🎤 Recording... (Press ENTER to stop)")
        
        def callback(indata, frames, time, status):
            if status:
                print(f"Recording status: {status}")
            if self.is_recording:
                self.recording.append(indata.copy())
        
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=callback
        )
        self.stream.start()
    
    def stop(self):
        """Stop recording and return audio data."""
        self.is_recording = False
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        
        if not self.recording:
            return None
        
        audio_data = np.concatenate(self.recording, axis=0)
        print(f"✅ Recording stopped ({len(audio_data)} samples, {len(audio_data)/self.sample_rate:.2f}s)")
        return audio_data
    
    def save_wav(self, audio_data, filename):
        """Save audio data as WAV file and return bytes."""
        if audio_data is None or len(audio_data) == 0:
            return None
        
        # Save to file
        sf.write(filename, audio_data, self.sample_rate)
        
        # Also return as bytes
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes((audio_data * 32767).astype(np.int16).tobytes())
        
        return buffer.getvalue()


def play_audio(audio_bytes):
    """Play audio from bytes."""
    try:
        # Save to temp file and play
        with open(TEMP_OUTPUT_FILE, 'wb') as f:
            f.write(audio_bytes)
        
        data, samplerate = sf.read(TEMP_OUTPUT_FILE)
        print(f"🔊 Playing NPC response ({len(data)} samples, {len(data)/samplerate:.2f}s)...")
        sd.play(data, samplerate)
        sd.wait()
        print("✅ Playback complete")
    except Exception as e:
        print(f"❌ Error playing audio: {e}")


async def check_server_health():
    """Check if the backend server is running."""
    health_url = "http://localhost:8000/health"
    print(f"🏥 Checking server health at {health_url}...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(health_url, timeout=5.0)
            if response.status_code == 200:
                print(f"✅ Server is healthy: {response.json()}")
                return True
            else:
                print(f"⚠️  Server responded with status {response.status_code}")
                return False
    except httpx.ConnectError:
        print("❌ Cannot connect to server. Is it running on port 8000?")
        print("   Start it with: uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


async def send_and_receive(audio_bytes):
    """
    Send audio to backend WebSocket and receive NPC response.
    
    Protocol:
    1. Connect to WebSocket
    2. Send audio as binary frames
    3. Send {"type": "end_utterance"} to signal completion
    4. Receive binary audio chunks and JSON events
    5. Play audio response
    """
    ws_url = f"{BACKEND_URL}/{PLAYER_ID}/{NPC_ID}"
    print(f"\n🔌 Connecting to {ws_url}...")
    
    try:
        # Increased timeout to 60 seconds for slower systems
        async with websockets.connect(
            ws_url, 
            open_timeout=60,
            close_timeout=10,
            ping_interval=20,
            ping_timeout=20
        ) as websocket:
            print("✅ Connected to backend!")
            
            # Send audio in chunks (simulate streaming)
            chunk_size = 4096
            total_chunks = (len(audio_bytes) + chunk_size - 1) // chunk_size
            
            print(f"\n📤 Sending audio ({len(audio_bytes)} bytes in {total_chunks} chunks)...")
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i+chunk_size]
                await websocket.send(chunk)
            
            # Signal end of utterance
            print("📤 Sending end_utterance signal...")
            await websocket.send(json.dumps({"type": "end_utterance"}))
            
            # Receive responses
            print("\n📥 Waiting for NPC response...\n")
            audio_chunks = []
            transcription = None
            npc_text = None
            
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    
                    # Binary frame = audio chunk
                    if isinstance(message, bytes):
                        audio_chunks.append(message)
                        print(f"  🔊 Received audio chunk #{len(audio_chunks)} ({len(message)} bytes)")
                    
                    # Text frame = event or signal
                    elif isinstance(message, str):
                        data = json.loads(message)
                        msg_type = data.get("type")
                        
                        if msg_type == "turn_complete":
                            print("\n✅ Turn complete!")
                            break
                        
                        elif msg_type == "transcription":
                            transcription = data.get("text", "")
                            print(f"\n  📝 Your speech: \"{transcription}\"")
                        
                        elif msg_type == "npc_text":
                            npc_text = data.get("text", "")
                            print(f"  💬 NPC says: \"{npc_text}\"")
                        
                        elif msg_type == "grammar_correction":
                            correction = data.get("data", {})
                            print(f"\n  ✏️  Grammar correction:")
                            print(f"      Original: {correction.get('original_text', 'N/A')}")
                            print(f"      Corrected: {correction.get('corrected_text', 'N/A')}")
                            if correction.get('mistakes'):
                                print(f"      Mistakes: {len(correction.get('mistakes'))} found")
                        
                        elif msg_type == "error":
                            print(f"\n❌ Server error: {data.get('message')}")
                            return
                        
                        else:
                            print(f"  📬 Event: {msg_type}")
                
                except asyncio.TimeoutError:
                    print("⏱️  Timeout waiting for response")
                    break
            
            # Play combined audio response
            if audio_chunks:
                print(f"\n🎵 Received {len(audio_chunks)} audio chunks total")
                combined_audio = b''.join(audio_chunks)
                play_audio(combined_audio)
            else:
                print("\n⚠️  No audio received from NPC")
    
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        print(f"\n💡 Troubleshooting tips:")
        print(f"   1. Make sure the server is running: uvicorn main:app --reload")
        print(f"   2. Check that the server started without errors")
        print(f"   3. Verify the WebSocket endpoint exists")
        print(f"   4. Try restarting the server with: Ctrl+C then uvicorn main:app --reload")
        import traceback
        traceback.print_exc()


async def main():
    """Main conversation loop."""
    print("="*80)
    print("VirtuLingo Voice Chat Test")
    print("="*80)
    print(f"\nBackend: {BACKEND_URL}")
    print(f"Player ID: {PLAYER_ID}")
    print(f"NPC ID: {NPC_ID}")
    print(f"Sample Rate: {SAMPLE_RATE}Hz")
    print("\n" + "="*80)
    
    # Check if server is running
    if not await check_server_health():
        print("\n⛔ Please start the backend server first!")
        return
    
    recorder = AudioRecorder()
    
    while True:
        print("\n\n" + "-"*80)
        input("Press ENTER to start recording (or Ctrl+C to quit)...")
        
        # Start recording
        recorder.start()
        
        # Wait for user to press ENTER again
        input()
        
        # Stop recording
        audio_data = recorder.stop()
        
        if audio_data is None or len(audio_data) == 0:
            print("⚠️  No audio recorded, try again")
            continue
        
        # Convert to WAV bytes
        audio_bytes = recorder.save_wav(audio_data, TEMP_INPUT_FILE)
        
        if audio_bytes:
            # Send to backend and receive response
            await send_and_receive(audio_bytes)
        else:
            print("❌ Failed to process audio")
        
        print("\n" + "-"*80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
