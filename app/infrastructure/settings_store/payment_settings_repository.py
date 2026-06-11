from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.payment_settings import PaymentSettings
from app.domain.repositories.payment_settings_repository import PaymentSettingsRepository
from app.infrastructure.db.models.payment_settings import PaymentSettingsModel

_SINGLE_ROW_ID = 1


def _to_entity(model: PaymentSettingsModel) -> PaymentSettings:
    return PaymentSettings(
        id=model.id,
        provider=model.provider,
        api_key=model.api_key,
        secret_key=model.secret_key,
        currency=model.currency,
        is_active=model.is_active,
        extra=dict(model.extra),
    )


class SqlPaymentSettingsRepository(PaymentSettingsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> PaymentSettings | None:
        model = await self._session.get(PaymentSettingsModel, _SINGLE_ROW_ID)
        return _to_entity(model) if model is not None else None

    async def save(self, settings: PaymentSettings) -> PaymentSettings:
        model = await self._session.get(PaymentSettingsModel, _SINGLE_ROW_ID)
        if model is None:
            model = PaymentSettingsModel(id=_SINGLE_ROW_ID)
            self._session.add(model)
        model.provider = settings.provider
        model.api_key = settings.api_key
        model.secret_key = settings.secret_key
        model.currency = settings.currency
        model.is_active = settings.is_active
        model.extra = settings.extra
        await self._session.flush()
        return _to_entity(model)
