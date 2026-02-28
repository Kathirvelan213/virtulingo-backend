from fastapi import APIRouter
from pydantic import BaseModel
from api.dependency import ConversationManagerDep

router = APIRouter()

class UtteranceRequest(BaseModel):
    player_id: str
    audio_base64: str

@router.post("/speak")
async def speak(request: UtteranceRequest, conv_manager: ConversationManagerDep):
    """
    Receive audio utterance, process via manager, and return audio reply.
    """
    # Real implementation would decode base64 audio
    audio_bytes = b"decoded_audio_content" 
    
    reply_audio = await conv_manager.handle_utterance(request.player_id, audio_bytes)
    
    return {"reply_audio_base64": "dummy_audio_response"} 
