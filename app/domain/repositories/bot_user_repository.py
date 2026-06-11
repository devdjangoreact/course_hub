from abc import ABC, abstractmethod

from app.domain.entities.bot_user import BotUser


class BotUserRepository(ABC):
    @abstractmethod
    async def get(self, user_id: int) -> BotUser | None: ...

    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> BotUser | None: ...

    @abstractmethod
    async def upsert(self, user: BotUser) -> BotUser: ...
