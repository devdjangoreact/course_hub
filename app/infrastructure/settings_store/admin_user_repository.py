from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.admin_user import AdminUser
from app.domain.repositories.admin_user_repository import AdminUserRepository
from app.infrastructure.db.models.admin_user import AdminUserModel


def _to_entity(model: AdminUserModel) -> AdminUser:
    return AdminUser(
        id=model.id,
        username=model.username,
        password_hash=model.password_hash,
        is_active=model.is_active,
        extra=dict(model.extra),
    )


class SqlAdminUserRepository(AdminUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_username(self, username: str) -> AdminUser | None:
        stmt = select(AdminUserModel).where(AdminUserModel.username == username)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def add(self, admin: AdminUser) -> AdminUser:
        model = AdminUserModel(
            username=admin.username,
            password_hash=admin.password_hash,
            is_active=admin.is_active,
            extra=admin.extra,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)
