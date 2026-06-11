from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.bot_user import BotUser
from app.domain.repositories.bot_user_repository import BotUserRepository
from app.infrastructure.db.models.bot_user import BotUserModel


def _to_entity(model: BotUserModel) -> BotUser:
    return BotUser(
        id=model.id,
        telegram_id=model.telegram_id,
        username=model.username,
        full_name=model.full_name,
        extra=dict(model.extra),
    )


class SqlBotUserRepository(BotUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int) -> BotUser | None:
        model = await self._session.get(BotUserModel, user_id)
        return _to_entity(model) if model is not None else None

    async def get_by_telegram_id(self, telegram_id: int) -> BotUser | None:
        stmt = select(BotUserModel).where(BotUserModel.telegram_id == telegram_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def upsert(self, user: BotUser) -> BotUser:
        stmt = select(BotUserModel).where(BotUserModel.telegram_id == user.telegram_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            model = BotUserModel(
                telegram_id=user.telegram_id,
                username=user.username,
                full_name=user.full_name,
                extra=user.extra,
            )
            self._session.add(model)
        else:
            model.username = user.username
            model.full_name = user.full_name
        await self._session.flush()
        return _to_entity(model)
