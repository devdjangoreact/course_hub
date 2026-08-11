from abc import ABC, abstractmethod

from app.domain.entities.telegram_channel import TelegramChannel


class TelegramChannelRepository(ABC):
    @abstractmethod
    async def list_by_bot(self, bot_id: int) -> list[TelegramChannel]: ...

    @abstractmethod
    async def get(self, channel_id: int) -> TelegramChannel | None: ...

    @abstractmethod
    async def save(self, channel: TelegramChannel) -> TelegramChannel: ...

    @abstractmethod
    async def list_course_ids(self, channel_id: int) -> list[int]: ...
