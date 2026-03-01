"""
WebSocket endpoint for the real-time conversation loop.

Unity connects here for each NPC conversation session.
Audio is sent as binary frames and NPC audio response is streamed back.

Protocol:
  Client → Server: binary WebSocket frames (PCM audio chunks)
  Server → Client: binary WebSocket frames (MP3 audio chunks from TTS)
  Server → Client: JSON text frames for corrections and metadata

Implements the STT → Grammar + LLM → TTS workflow from the system design:
  1. Streaming STT: Audio chunks → transcription
  2. Parallel execution:
     - Grammar correction (async, non-blocking) → pushes event to Unity
     - LLM conversation → TTS → streams audio back
  3. Real-time event notifications via WebSocket
"""
import asyncio
import json
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from api.dependency import ConversationManagerDep, GrammarManagerDep, DialogueOrchestratorDep

router = APIRouter()

# Store active WebSocket connections for event broadcasting
_active_connections: Dict[str, WebSocket] = {}


async def event_broadcaster(event: dict) -> None:
    """
    Callback for broadcasting events to Unity clients via WebSocket.
    Called by the DialogueOrchestrator when events occur (e.g., grammar corrections).
    """
    player_id = event.get("player_id")
    if player_id and player_id in _active_connections:
        websocket = _active_connections[player_id]
        try:
            await websocket.send_text(json.dumps(event))
        except Exception as e:
            print(f"[WebSocket] Failed to broadcast event to {player_id}: {e}")


@router.websocket("/ws/test")
async def test_websocket(websocket: WebSocket):
    """Simple test WebSocket without dependencies."""
    print("[Test WS] Connection attempt")
    await websocket.accept()
    print("[Test WS] Connection accepted")
    await websocket.send_text("Hello from server!")
    await websocket.close()


@router.websocket("/ws/{player_id}/{npc_id}")
async def conversation_websocket(
    websocket: WebSocket,
    player_id: str,
    npc_id: str,
):
    """
    WebSocket endpoint for the live STT → LLM → TTS loop.

    This implements the complete workflow from the system design:
    1. Receive audio chunks from Unity
    2. STT: Transcribe player speech
    3. Parallel execution:
       - Grammar correction (async) → sends event to Unity
       - LLM conversation → TTS → streams audio back
    4. Stream NPC audio response back to Unity

    Unity Client Protocol:
    ───────────────────────────────────────────────────────────────────────
    Client → Server:
      - Binary frames: Raw audio bytes (PCM 16kHz mono)
      - JSON text: {"type": "end_utterance"} to signal speaking is done
      - JSON text: {"type": "streaming", "enabled": true} for streaming mode

    Server → Client:
      - Binary frames: MP3/WAV audio chunks for NPC voice
      - JSON text: {"type": "grammar_correction", "data": {...}}
      - JSON text: {"type": "turn_complete"}
      - JSON text: {"type": "transcription", "text": "..."} (optional)
    """
    # Manually get orchestrator from container
    orchestrator = websocket.app.state.container.dialogue_orchestrator
    
    print(f"[WebSocket] Connection attempt from player_id={player_id}, npc_id={npc_id}")
    print(f"[WebSocket] Orchestrator: {orchestrator}")
    
    await websocket.accept()
    print(f"[WebSocket] Connection accepted for player_id={player_id}")
    
    # Register connection for event broadcasting
    _active_connections[player_id] = websocket
    
    try:
        audio_buffer = bytearray()
        streaming_mode = False  # Can be toggled by client

        while True:
            message = await websocket.receive()

            if "bytes" in message:
                # Accumulate audio chunks
                audio_buffer.extend(message["bytes"])

            elif "text" in message:
                data = json.loads(message["text"])
                msg_type = data.get("type")

                if msg_type == "end_utterance":
                    # Complete utterance received, process it
                    if not audio_buffer:
                        continue

                    print(f"[WebSocket] Processing {len(audio_buffer)} bytes of audio...")
                    
                    # Stream NPC audio response chunks back to Unity
                    chunk_count = 0
                    try:
                        async for item in orchestrator.process_conversation_turn(
                            player_id=player_id,
                            npc_id=npc_id,
                            audio_bytes=bytes(audio_buffer),
                        ):
                            # Check if it's audio (bytes) or metadata (dict)
                            if isinstance(item, bytes):
                                chunk_count += 1
                                print(f"[WebSocket] Sending audio chunk #{chunk_count} ({len(item)} bytes)")
                                await websocket.send_bytes(item)
                            elif isinstance(item, dict):
                                # Send metadata events (transcription, npc_text, etc.)
                                print(f"[WebSocket] Sending metadata event: {item.get('type')}")
                                await websocket.send_text(json.dumps(item))
                        
                        print(f"[WebSocket] Sent {chunk_count} audio chunks total")
                    except Exception as e:
                        print(f"[WebSocket] Error during processing: {e}")
                        import traceback
                        traceback.print_exc()
                        raise

                    # Signal turn complete
                    print("[WebSocket] Sending turn_complete signal")
                    await websocket.send_text(json.dumps({"type": "turn_complete"}))
                    audio_buffer.clear()

                elif msg_type == "streaming":
                    # Toggle streaming mode
                    streaming_mode = data.get("enabled", False)
                    await websocket.send_text(json.dumps({
                        "type": "streaming_mode",
                        "enabled": streaming_mode,
                    }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except:
            pass
        await websocket.close()
    finally:
        # Cleanup connection
        if player_id in _active_connections:
            del _active_connections[player_id]


@router.websocket("/ws/stream/{player_id}/{npc_id}")
async def conversation_websocket_streaming(
    websocket: WebSocket,
    player_id: str,
    npc_id: str,
    orchestrator: DialogueOrchestratorDep,
):
    """
    True streaming WebSocket endpoint using streaming STT (Deepgram).
    
    This variant processes audio chunks in real-time as they arrive,
    enabling even lower latency than batch mode.
    
    Unity Client Protocol:
    ───────────────────────────────────────────────────────────────────────
    Client → Server:
      - Binary frames: Audio chunks (sent continuously while speaking)
      - JSON text: {"type": "start_utterance"} when player starts speaking
      - JSON text: {"type": "stop_utterance"} when player stops speaking
    
    Server → Client:
      - Binary frames: NPC audio chunks (streamed)
      - JSON text: Events (grammar corrections, transcriptions)
    """
    await websocket.accept()
    _active_connections[player_id] = websocket
    
    try:
        audio_queue = asyncio.Queue()
        recording = False
        
        async def audio_stream_generator():
            """Generator that yields audio chunks from the queue."""
            while recording:
                try:
                    chunk = await asyncio.wait_for(audio_queue.get(), timeout=5.0)
                    yield chunk
                except asyncio.TimeoutError:
                    break
        
        while True:
            message = await websocket.receive()
            
            if "bytes" in message and recording:
                # Add audio chunk to queue
                await audio_queue.put(message["bytes"])
            
            elif "text" in message:
                data = json.loads(message["text"])
                msg_type = data.get("type")
                
                if msg_type == "start_utterance":
                    recording = True
                    await audio_queue.put(b"")  # Prime the pump
                
                elif msg_type == "stop_utterance":
                    recording = False
                    
                    # Process the streaming conversation
                    async for audio_chunk in orchestrator.process_streaming_conversation(
                        player_id=player_id,
                        npc_id=npc_id,
                        audio_stream=audio_stream_generator(),
                    ):
                        await websocket.send_bytes(audio_chunk)
                    
                    await websocket.send_text(json.dumps({"type": "turn_complete"}))
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except:
            pass
        await websocket.close()
    finally:
        if player_id in _active_connections:
            del _active_connections[player_id]


@router.post("/{player_id}/correct")
async def correct_utterance(
    player_id: str,
    body: dict,
    orchestrator: DialogueOrchestratorDep,
):
    """
    REST endpoint for explicit grammar correction.
    
    Unity sends the transcribed player utterance and receives structured feedback.
    This bypasses the real-time conversation flow for explicit grammar checks.
    """
    utterance = body.get("utterance", "")
    language = body.get("language", "French")

    result = await orchestrator.get_grammar_correction(
        player_id=player_id,
        player_text=utterance,
        language=language,
    )

    return result


@router.get("/{player_id}/mistakes")
async def get_mistake_summary(
    player_id: str,
    grammar_manager: GrammarManagerDep,
):
    """
    Get the player's top recurring grammar mistake categories.
    Used for generating targeted review sessions.
    """
    return await grammar_manager.get_mistake_summary(player_id)


@router.post("/{player_id}/{npc_id}/conversation")
async def start_conversation(
    player_id: str,
    npc_id: str,
    orchestrator: DialogueOrchestratorDep,
):
    """
    REST endpoint for non-WebSocket conversation (testing/debugging).
    
    Expects JSON body:
    {
        "audio_base64": "...",  // Base64-encoded audio
        "format": "pcm",        // Audio format
    }
    
    Returns:
    {
        "npc_audio_base64": "...",
        "npc_text": "...",
        "player_text": "..."
    }
    """
    import base64
    
    # This would be implemented for REST-based testing
    return {
        "error": "Use WebSocket endpoint /ws/{player_id}/{npc_id} for conversations"
    }
