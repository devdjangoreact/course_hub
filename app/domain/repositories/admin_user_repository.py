from abc import ABC, abstractmethod

from app.domain.entities.admin_user import AdminUser


class AdminUserRepository(ABC):
    @abstractmethod
    async def get_by_username(self, username: str) -> AdminUser | None: ...

    @abstractmethod
    async def add(self, admin: AdminUser) -> AdminUser: ...
