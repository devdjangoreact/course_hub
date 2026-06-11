import pytest

from app.application.services.localization_service import LocalizationService
from app.bot.handlers.start import handle_start
from app.domain.entities.bot_user import BotUser
from app.domain.repositories.bot_user_repository import BotUserRepository
from tests.unit.test_localization_service import FakeLanguageRepository


class FakeTelegramUser:
    id = 123
    username = "student"
    full_name = "Student User"


class FakeMessage:
    def __init__(self) -> None:
        self.from_user = FakeTelegramUser()
        self.answers: list[str] = []

    async def answer(self, text: str, reply_markup: object | None = None) -> None:
        self.answers.append(text)


class FakeBotUserRepository(BotUserRepository):
    def __init__(self) -> None:
        self.users: dict[int, BotUser] = {}

    async def get(self, user_id: int) -> BotUser | None:
        return next((user for user in self.users.values() if user.id == user_id), None)

    async def get_by_telegram_id(self, telegram_id: int) -> BotUser | None:
        return self.users.get(telegram_id)

    async def upsert(self, user: BotUser) -> BotUser:
        saved = BotUser(
            id=user.id or 1,
            telegram_id=user.telegram_id,
            username=user.username,
            full_name=user.full_name,
            preferred_language=user.preferred_language,
            extra=user.extra,
        )
        self.users[user.telegram_id] = saved
        return saved


@pytest.mark.asyncio
async def test_new_user_is_asked_to_choose_language() -> None:
    message = FakeMessage()
    bot_users = FakeBotUserRepository()
    localization = LocalizationService(FakeLanguageRepository())

    await handle_start(message, bot_users, localization)

    assert message.answers == ["Оберіть мову інтерфейсу:"]


@pytest.mark.asyncio
async def test_returning_user_gets_saved_language_menu() -> None:
    message = FakeMessage()
    bot_users = FakeBotUserRepository()
    localization = LocalizationService(FakeLanguageRepository())
    await bot_users.upsert(
        BotUser(id=None, telegram_id=123, username="student", preferred_language="en")
    )

    await handle_start(message, bot_users, localization)

    assert message.answers == ["Welcome to Course Hub! Browse courses by category or search."]
