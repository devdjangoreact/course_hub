from fastapi import FastAPI
from sqladmin import Admin

from app.admin.auth import AdminAuth
from app.admin.views import ALL_VIEWS
from app.core.config import Settings
from app.core.database import Database


def setup_admin(app: FastAPI, database: Database, settings: Settings) -> Admin:
    admin = Admin(
        app,
        engine=database.engine,
        authentication_backend=AdminAuth(settings.admin_session_secret, database),
        title="Course Hub Admin",
    )
    for view in ALL_VIEWS:
        admin.add_view(view)
    return admin
