from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.bot_settings import BotSettings
from app.domain.repositories.bot_settings_repository import BotSettingsRepository
from app.infrastructure.db.models.bot_settings import BotSettingsModel

_SINGLE_ROW_ID = 1


def _to_entity(model: BotSettingsModel) -> BotSettings:
    return BotSettings(
        id=model.id,
        bot_token=model.bot_token,
        backend_url=model.backend_url,
        is_active=model.is_active,
        extra=dict(model.extra),
    )


class SqlBotSettingsRepository(BotSettingsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> BotSettings | None:
        model = await self._session.get(BotSettingsModel, _SINGLE_ROW_ID)
        return _to_entity(model) if model is not None else None

    async def save(self, settings: BotSettings) -> BotSettings:
        model = await self._session.get(BotSettingsModel, _SINGLE_ROW_ID)
        if model is None:
            model = BotSettingsModel(id=_SINGLE_ROW_ID)
            self._session.add(model)
        model.bot_token = settings.bot_token
        model.backend_url = settings.backend_url
        model.is_active = settings.is_active
        model.extra = settings.extra
        await self._session.flush()
        return _to_entity(model)
