from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, ExtraMixin


class SupportedLanguageModel(Base, ExtraMixin):
    __tablename__ = "supported_languages"

    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    native_name: Mapped[str] = mapped_column()
    is_default: Mapped[bool] = mapped_column(default=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
