from abc import ABC, abstractmethod
from typing import Any, Dict, List

class IWorldStateRepository(ABC):
    @abstractmethod
    async def get_player_state(self, player_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def update_player_state(self, player_id: str, state: Dict[str, Any]) -> None:
        pass

class IMistakeRepository(ABC):
    @abstractmethod
    async def log_mistake(self, player_id: str, mistake_data: Dict[str, Any]) -> None:
        pass

class IPlayerProfileRepository(ABC):
    @abstractmethod
    async def get_profile(self, player_id: str) -> Dict[str, Any]:
        pass
