from abc import ABC, abstractmethod


class RateLimiter(ABC):
    @abstractmethod
    async def allow(self, key: str) -> bool:
        """Return True if the action is permitted for the key within the window."""
