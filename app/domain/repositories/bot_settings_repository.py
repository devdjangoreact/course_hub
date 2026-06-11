from abc import ABC, abstractmethod

from app.domain.entities.bot_settings import BotSettings


class BotSettingsRepository(ABC):
    @abstractmethod
    async def get(self) -> BotSettings | None: ...

    @abstractmethod
    async def save(self, settings: BotSettings) -> BotSettings: ...
