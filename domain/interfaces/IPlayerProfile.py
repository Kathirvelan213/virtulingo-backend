from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


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
