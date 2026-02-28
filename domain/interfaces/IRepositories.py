from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IWorldStateRepository(ABC):
    """Manages real-time player + world state stored in Redis."""

    @abstractmethod
    async def get_player_state(self, player_id: str) -> Dict[str, Any]:
        """
        Returns the current full state dict for a player.
        Keys include: position, scene_id, object_in_hand, nearby_npcs, active_quest, language, proficiency_level.
        """
        ...

    @abstractmethod
    async def update_player_state(self, player_id: str, patch: Dict[str, Any]) -> None:
        """Atomically merge the patch dict into the existing player state."""
        ...

    @abstractmethod
    async def get_conversation_history(
        self, player_id: str, npc_id: str, window: int = 10
    ) -> List[Dict[str, str]]:
        """Return the last `window` turns of dialogue with a specific NPC."""
        ...

    @abstractmethod
    async def append_conversation_turn(
        self, player_id: str, npc_id: str, role: str, content: str
    ) -> None:
        """Append a single dialogue turn to the conversation history list."""
        ...


class IMistakeRepository(ABC):
    """Persists grammar mistake logs to Postgres."""

    @abstractmethod
    async def log_mistake(
        self, player_id: str, category: str, original: str, correction: str, explanation: str
    ) -> None:
        """Persist a single grammar mistake event."""
        ...

    @abstractmethod
    async def get_top_mistakes(
        self, player_id: str, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Return the most frequent mistake categories for a player, sorted by count desc."""
        ...

    @abstractmethod
    async def get_recent_mistakes(
        self, player_id: str, since_minutes: int = 15
    ) -> List[Dict[str, Any]]:
        """Return all mistakes logged in the last N minutes for review session generation."""
        ...


class INPCRepository(ABC):
    """Provides NPC personality profiles."""

    @abstractmethod
    async def get_npc_profile(self, npc_id: str) -> Dict[str, Any]:
        """
        Returns NPC profile dict with keys:
          name, personality, language_complexity (A1–C2), voice_id,
          emotional_tone, backstory, relationship_score.
        """
        ...

    @abstractmethod
    async def update_relationship_score(
        self, npc_id: str, player_id: str, delta: float
    ) -> None:
        """Adjust the relationship score between a player and NPC."""
        ...


class IPlayerProfileRepository(ABC):
    """Manages persistent player language learner profiles."""

    @abstractmethod
    async def get_profile(self, player_id: str) -> Dict[str, Any]:
        """Return proficiency level, target language, native language, and session stats."""
        ...

    @abstractmethod
    async def update_proficiency(self, player_id: str, new_level: str) -> None:
        """Update the player's assessed proficiency level (A1–C2)."""
        ...
