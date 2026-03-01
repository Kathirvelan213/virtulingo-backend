"""
Simple in-memory player profile repository for testing.
"""
from typing import Any, Dict
from domain.interfaces.IPlayerProfile import IPlayerProfileRepository


class InMemoryPlayerProfileRepository(IPlayerProfileRepository):
    """
    Mock implementation of player profile repository.
    Returns a default profile for any player_id.
    """
    
    def __init__(self):
        self._profiles = {}
    
    async def get_profile(self, player_id: str) -> Dict[str, Any]:
        """Return proficiency level, target language, native language, and session stats."""
        # Return cached profile or create a default one
        if player_id not in self._profiles:
            self._profiles[player_id] = {
                "player_id": player_id,
                "target_language": "Spanish",
                "native_language": "English",
                "proficiency_level": "A2",  # Elementary (CEFR scale: A1-C2)
                "session_count": 0,
                "total_mistakes": 0,
                "last_session": None,
            }
        return self._profiles[player_id]
    
    async def update_proficiency(self, player_id: str, new_level: str) -> None:
        """Update the player's assessed proficiency level (A1–C2)."""
        if player_id in self._profiles:
            self._profiles[player_id]["proficiency_level"] = new_level
        else:
            # Create profile with updated level
            profile = await self.get_profile(player_id)
            profile["proficiency_level"] = new_level
