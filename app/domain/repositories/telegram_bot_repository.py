from abc import ABC, abstractmethod

from app.domain.entities.telegram_bot import TelegramBot


class TelegramBotRepository(ABC):
    @abstractmethod
    async def list_active(self) -> list[TelegramBot]: ...

    @abstractmethod
    async def get_by_username(self, username: str) -> TelegramBot | None: ...

    @abstractmethod
    async def get_by_token(self, token: str) -> TelegramBot | None: ...

    @abstractmethod
    async def get(self, bot_id: int) -> TelegramBot | None: ...

    @abstractmethod
    async def save(self, bot: TelegramBot) -> TelegramBot: ...
