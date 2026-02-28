-- VirtuLingo PostgreSQL Schema
-- Run this once to initialize the database.

-- NPC base profiles
CREATE TABLE IF NOT EXISTS npcs (
    npc_id              TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    personality         TEXT NOT NULL,
    backstory           TEXT NOT NULL,
    language_complexity TEXT NOT NULL,   -- CEFR: A1, A2, B1, B2, C1, C2
    emotional_tone      TEXT NOT NULL,
    voice_id            TEXT NOT NULL    -- ElevenLabs voice ID
);

-- NPC-Player relationship scores
CREATE TABLE IF NOT EXISTS npc_relationships (
    npc_id    TEXT REFERENCES npcs(npc_id) ON DELETE CASCADE,
    player_id TEXT NOT NULL,
    score     FLOAT DEFAULT 0.0,         -- clamped -1.0 to 1.0
    PRIMARY KEY (npc_id, player_id)
);

-- Grammar mistake log
CREATE TABLE IF NOT EXISTS grammar_mistakes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id   TEXT NOT NULL,
    category    TEXT NOT NULL,
    original    TEXT NOT NULL,
    correction  TEXT NOT NULL,
    explanation TEXT NOT NULL,
    severity    INTEGER DEFAULT 1,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Index for fast aggregation queries by player + recency
CREATE INDEX IF NOT EXISTS idx_mistakes_player_time
    ON grammar_mistakes (player_id, created_at DESC);

-- ── Seed Data: Example NPCs ──────────────────────────────────────────────────
INSERT INTO npcs (npc_id, name, personality, backstory, language_complexity, emotional_tone, voice_id)
VALUES
    ('baker_pierre',
     'Pierre',
     'a grumpy but secretly warm-hearted baker',
     'Pierre has run his boulangerie in Lyon for 30 years. He has little patience for fumbling tourists, but secretly enjoys teaching them about bread.',
     'A2',
     'gruff and impatient, but occasionally shows warmth',
     'YOUR_ELEVENLABS_VOICE_ID_MALE_FRENCH'),

    ('student_claire',
     'Claire',
     'an enthusiastic university student studying literature',
     'Claire is studying French literature at Lyon University. She is eager to practice her English but will speak only French out of principle.',
     'B2',
     'warm, energetic, and curious',
     'YOUR_ELEVENLABS_VOICE_ID_FEMALE_FRENCH'),

    ('officer_dubois',
     'Inspecteur Dubois',
     'a formal, by-the-book police inspector',
     'Inspecteur Dubois is a veteran of the Lyon police with a strict adherence to rules. He is polite but formal and uses complex formal language.',
     'C1',
     'formal, precise, slightly intimidating',
     'YOUR_ELEVENLABS_VOICE_ID_MALE_FORMAL')
ON CONFLICT (npc_id) DO NOTHING;
