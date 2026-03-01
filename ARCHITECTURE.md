# VirtuLingo Backend Architecture

## Overview

VirtuLingo implements a real-time, event-driven architecture for AI-powered language learning conversations. The system orchestrates Speech-to-Text (STT), Large Language Models (LLM), and Text-to-Speech (TTS) services to create immersive, context-aware dialogue with virtual NPCs.

## System Workflow: STT → Grammar + LLM → TTS

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Unity Client                                │
│  (Player speaks into microphone)                                    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Audio Stream (WebSocket)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    WebSocket Endpoint                                │
│              /ws/{player_id}/{npc_id}                               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  DialogueOrchestrator                                │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ STEP 1: Speech-to-Text (STT)                                 │  │
│  │ • Whisper (local, faster-whisper)                            │  │
│  │ • Transcribes player audio → text                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ STEP 2: Parallel Processing (Non-Blocking)                   │  │
│  │                                                               │  │
│  │  ┌─────────────────────┐      ┌────────────────────────┐    │  │
│  │  │ Grammar Correction  │      │ Conversation Engine    │    │  │
│  │  │ (Async Background)  │      │ (Primary Path)         │    │  │
│  │  ├─────────────────────┤      ├────────────────────────┤    │  │
│  │  │ • Gemini LLM        │      │ • Fetch context        │    │  │
│  │  │ • JSON output       │      │   (Redis world state,  │    │  │
│  │  │ • Detects mistakes  │      │    NPC profile,        │    │  │
│  │  │ • Logs to DB        │      │    conversation hist)  │    │  │
│  │  │ • Fires event →     │      │ • Build dynamic prompt │    │  │
│  │  │   Unity (non-block) │      │ • Gemini LLM (stream)  │    │  │
│  │  └─────────────────────┘      └────────────┬───────────┘    │  │
│  │                                             │                │  │
│  └─────────────────────────────────────────────┼────────────────┘  │
│                                                 │                   │
└─────────────────────────────────────────────────┼───────────────────┘
                                                  │ Text Stream
                                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: Text-to-Speech (TTS)                                       │
│  • Coqui TTS (local)                                                │
│  • Streams audio chunks as LLM generates text                       │
│  • Sentence-boundary buffering for natural speech                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Audio Stream
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Unity Client                                │
│  (NPC speaks, player hears response)                                │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. DialogueOrchestrator (`application/DialogueOrchestrator.py`)

**Primary workflow coordinator** that implements the complete STT → Grammar + LLM → TTS pipeline.

**Key Methods:**
- `process_conversation_turn()` - Full conversation round-trip (batch mode)
- `process_streaming_conversation()` - Streaming variant (real-time transcription)
- `_generate_npc_response_stream()` - LLM → TTS streaming pipeline
- `_process_grammar_correction_async()` - Background grammar analysis

**Design Principles:**
- Grammar correction NEVER blocks the conversation flow
- LLM and TTS use streaming to minimize latency
- Context injection from Redis world state
- Event-driven notifications via callback

### 2. AI Services

#### LLM: Google Gemini (`infrastructures/GeminiLLM.py`)
- **Model:** gemini-1.5-flash (fast, cost-effective)
- **Streaming:** Async text generation for low-latency conversations
- **Structured Output:** JSON mode for grammar corrections
- **Temperature:** 0.2 for grammar, 0.8 for conversation

#### STT: Whisper (`infrastructures/SpeechToText.py`)
- **Model:** faster-whisper (small)
- **Mode:** Local CPU inference (int8 quantization)
- **Features:** Streaming support, automatic punctuation

#### TTS: Coqui TTS (`infrastructures/TextToSpeech.py`)
- **Model:** Tacotron2-DDC (LJSpeech)
- **Mode:** Local generation
- **Streaming:** Sentence-boundary buffering

### 3. Event Bus (`infrastructures/events.py`)

Lightweight event system for asynchronous messaging:
- **Events:** `grammar_correction`, `conversation_turn`, `player_moved`, etc.
- **Implementation:** In-memory for development
- **Production:** Can be replaced with NATS, Redis Streams, or Kafka

### 4. WebSocket Endpoints (`api/routers/conversations.py`)

#### `/ws/{player_id}/{npc_id}` - Batch Mode
- Client sends complete audio utterances
- Server processes and streams NPC response

#### `/ws/stream/{player_id}/{npc_id}` - Streaming Mode
- Client streams audio chunks in real-time
- Server uses streaming STT for lower latency

### 5. State Management

#### Redis (World State)
- Player position, scene context
- Objects in hand, active quests
- Nearby NPCs, relationship scores
- Conversation history (last 10 turns)

#### PostgreSQL (Persistent Data)
- NPC profiles (personality, language complexity)
- Grammar mistakes (for review sessions)
- Player profiles (proficiency level)

## Latency Optimization

### Target: < 2s end-to-end latency

1. **Streaming STT** - Transcription starts during speech
2. **Parallel Grammar Processing** - Doesn't block conversation
3. **Streaming LLM** - Response generation starts immediately
4. **Streaming TTS** - Audio playback begins while generating
5. **Redis Context Cache** - O(1) world state retrieval
6. **Sentence Buffering** - Natural speech rhythm without delay

## Configuration

### Environment Variables
```bash
# Required
GOOGLE_API_KEY=your-gemini-api-key
SUPABASE_DB_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0

# Optional
GEMINI_MODEL=gemini-1.5-flash  # or gemini-1.5-pro
```

### Service Selection
- **LLM:** Google Gemini (cloud API)
- **STT:** Whisper (local, CPU)
- **TTS:** Coqui TTS (local, CPU)

## API Endpoints

### WebSocket
- `WS /api/conversations/ws/{player_id}/{npc_id}` - Main conversation loop
- `WS /api/conversations/ws/stream/{player_id}/{npc_id}` - Streaming variant

### REST
- `POST /api/conversations/{player_id}/correct` - Explicit grammar check
- `GET /api/conversations/{player_id}/mistakes` - Top mistake categories
- `POST /api/conversations/{player_id}/{npc_id}/conversation` - Debug endpoint

## Dependency Injection

Services are wired in `_bootstrap/bootstrap.py`:

```
Container
├── event_bus: EventBus
├── llm_service: GeminiLLM
├── stt_service: WhisperSTT
├── tts_service: CoquiTTS
├── world_state_repo: RedisWorldStateRepository
├── mistake_repo: PostgresMistakeRepository
├── npc_repo: PostgresNPCRepository
└── dialogue_orchestrator: DialogueOrchestrator
```

## Future Enhancements

1. **Production Event Bus** - Replace in-memory with NATS or Kafka
2. **Horizontal Scaling** - Stateless orchestrators with shared Redis
3. **WebRTC Audio** - UDP transport for lower network jitter
4. **Prompt Caching** - Cache common LLM responses
5. **Fine-tuned Grammar Model** - Smaller, faster grammar correction
6. **Multi-language Support** - Dynamic language switching
