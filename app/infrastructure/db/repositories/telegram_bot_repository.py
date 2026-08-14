from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.telegram_bot import TelegramBot
from app.domain.repositories.telegram_bot_repository import TelegramBotRepository
from app.infrastructure.db.models.telegram_bot import TelegramBotModel


def _to_entity(model: TelegramBotModel) -> TelegramBot:
    return TelegramBot(
        id=model.id,
        username=model.username,
        token=model.token,
        webhook_secret=model.webhook_secret,
        is_active=model.is_active,
        title=model.title,
        notes=model.notes,
        extra=dict(model.extra),
    )


class SqlTelegramBotRepository(TelegramBotRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[TelegramBot]:
        stmt = select(TelegramBotModel).where(TelegramBotModel.is_active.is_(True))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(row) for row in rows]

    async def get_by_username(self, username: str) -> TelegramBot | None:
        stmt = select(TelegramBotModel).where(TelegramBotModel.username == username)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def get_by_token(self, token: str) -> TelegramBot | None:
        stmt = select(TelegramBotModel).where(TelegramBotModel.token == token)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def get(self, bot_id: int) -> TelegramBot | None:
        model = await self._session.get(TelegramBotModel, bot_id)
        return _to_entity(model) if model is not None else None

    async def save(self, bot: TelegramBot) -> TelegramBot:
        if bot.id is not None:
            model = await self._session.get(TelegramBotModel, bot.id)
            if model is None:
                model = TelegramBotModel(id=bot.id)
                self._session.add(model)
        else:
            model = TelegramBotModel()
            self._session.add(model)
        model.username = bot.username
        model.token = bot.token
        model.webhook_secret = bot.webhook_secret
        model.is_active = bot.is_active
        model.title = bot.title
        model.notes = bot.notes
        model.extra = bot.extra
        await self._session.flush()
        return _to_entity(model)
