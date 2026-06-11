from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.core.database import Database
from app.infrastructure.security.password import verify_password
from app.infrastructure.settings_store.admin_user_repository import SqlAdminUserRepository

_SESSION_KEY = "admin_user"


class AdminAuth(AuthenticationBackend):
    """Authenticates the admin panel against persisted AdminUser accounts."""

    def __init__(self, secret_key: str, database: Database) -> None:
        super().__init__(secret_key=secret_key)
        self._database = database

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))
        async with self._database.session_factory() as session:
            admin = await SqlAdminUserRepository(session).get_by_username(username)
        if admin is None or not admin.is_active:
            return False
        if not verify_password(password, admin.password_hash):
            return False
        request.session[_SESSION_KEY] = username
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return _SESSION_KEY in request.session
