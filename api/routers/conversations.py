"""
WebSocket endpoint for the real-time conversation loop.

Unity connects here for each NPC conversation session.
Audio is sent as binary frames and NPC audio response is streamed back.

Protocol:
  Client → Server: binary WebSocket frames (PCM audio chunks)
  Server → Client: binary WebSocket frames (MP3 audio chunks from TTS)
  Server → Client: JSON text frames for corrections and metadata
"""
import base64
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.dependency import ConversationManagerDep, GrammarManagerDep

router = APIRouter()


@router.websocket("/ws/{player_id}/{npc_id}")
async def conversation_websocket(
    websocket: WebSocket,
    player_id: str,
    npc_id: str,
    conv_manager: ConversationManagerDep,
):
    """
    WebSocket endpoint for the live STT → LLM → TTS loop.

    Unity sends:
      - Binary frames: raw audio bytes (PCM 16kHz mono)
      - JSON text: {"type": "end_utterance"} to signal speaking is done

    Server responds:
      - Binary frames: MP3 audio chunks for NPC voice
      - JSON text: {"type": "grammar_correction", "data": {...}}
      - JSON text: {"type": "turn_complete"} when NPC is done speaking
    """
    await websocket.accept()

    try:
        audio_buffer = bytearray()

        while True:
            message = await websocket.receive()

            if "bytes" in message:
                # Accumulate audio chunks
                audio_buffer.extend(message["bytes"])

            elif "text" in message:
                data = json.loads(message["text"])

                if data.get("type") == "end_utterance":
                    if not audio_buffer:
                        continue

                    # Stream NPC audio response chunks back to Unity
                    async for audio_chunk in conv_manager.handle_utterance_stream(
                        player_id=player_id,
                        npc_id=npc_id,
                        audio_bytes=bytes(audio_buffer),
                    ):
                        await websocket.send_bytes(audio_chunk)

                    await websocket.send_text(json.dumps({"type": "turn_complete"}))
                    audio_buffer.clear()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        await websocket.close()


@router.post("/{player_id}/correct")
async def correct_utterance(
    player_id: str,
    body: dict,
    grammar_manager: GrammarManagerDep,
):
    """
    REST endpoint for explicit grammar correction.
    Unity sends the transcribed player utterance and receives structured feedback.
    """
    utterance = body.get("utterance", "")
    language = body.get("language", "French")

    result = await grammar_manager.correct(
        player_id=player_id,
        utterance=utterance,
        target_language=language,
    )

    return {
        "mistake_found": result.mistake_found,
        "category": result.category,
        "original": result.original,
        "correction": result.correction,
        "explanation": result.explanation,
        "severity": result.severity,
    }


@router.get("/{player_id}/mistakes")
async def get_mistake_summary(
    player_id: str,
    grammar_manager: GrammarManagerDep,
):
    """Return the player's top recurring grammar mistake categories."""
    return await grammar_manager.get_mistake_summary(player_id)
