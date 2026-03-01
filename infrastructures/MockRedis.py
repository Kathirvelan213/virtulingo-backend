"""
Mock Redis implementation for testing without a Redis server.
"""
from typing import Optional, Dict


class MockRedis:
    """In-memory mock Redis for testing."""
    
    def __init__(self):
        self._data: Dict[str, str] = {}
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        return self._data.get(key)
    
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set key-value pair with optional expiration."""
        self._data[key] = value
        return True
    
    async def delete(self, key: str) -> int:
        """Delete key."""
        if key in self._data:
            del self._data[key]
            return 1
        return 0
    
    async def exists(self, key: str) -> int:
        """Check if key exists."""
        return 1 if key in self._data else 0
    
    async def expire(self, key: str, seconds: int) -> int:
        """Mock expire (does nothing in mock)."""
        return 1 if key in self._data else 0
    
    async def keys(self, pattern: str) -> list:
        """Get all keys matching pattern."""
        # Simple pattern matching
        if pattern == "*":
            return list(self._data.keys())
        # Add more pattern matching if needed
        return [k for k in self._data.keys() if pattern.replace("*", "") in k]
    
    async def close(self):
        """Mock close."""
        pass
    
    async def ping(self) -> bool:
        """Mock ping."""
        return True
