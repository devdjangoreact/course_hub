from decimal import Decimal

import pytest

from app.application.errors import NotFoundError
from app.application.services.catalog_service import LocalizedCourse
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
    def __init__(self, text: str = "/start") -> None:
        self.from_user = FakeTelegramUser()
        self.text = text
        self.bot = None
        self.answers: list[str] = []
        self.markups: list[object | None] = []

    async def answer(self, text: str, reply_markup: object | None = None) -> None:
        self.answers.append(text)
        self.markups.append(reply_markup)


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


class FakeCatalogService:
    async def get_localized_course_by_catalog_slug(
        self, catalog_slug: str, language: str
    ) -> LocalizedCourse:
        if catalog_slug != "stable-course":
            raise NotFoundError("Course not found")
        return LocalizedCourse(
            id=7,
            name="Stable Course",
            description="Course post",
            category_id=1,
            price=Decimal("12.00"),
            link="https://download.example/course",
            language=language,
            fallback_used=True,
            extra={
                "catalog_slug": catalog_slug,
                "download_link": "https://download.example/course",
                "invite_link": "https://t.me/+catalog",
                "channel_id": -1001,
                "promo_message_ids": [10],
                "full_message_ids": [11],
            },
        )


class FakeOrderService:
    def __init__(self, paid: bool) -> None:
        self.paid = paid

    async def has_paid_course(self, telegram_id: int, course_id: int) -> bool:
        return self.paid


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


@pytest.mark.asyncio
async def test_course_deep_link_shows_order_without_download_for_unpaid_user() -> None:
    message = FakeMessage("/start course_stable-course")
    bot_users = FakeBotUserRepository()
    localization = LocalizationService(FakeLanguageRepository())

    await handle_start(
        message,
        bot_users,
        localization,
        FakeCatalogService(),
        FakeOrderService(paid=False),
    )

    combined = "\n".join(message.answers)
    assert "Stable Course" in combined
    assert "https://t.me/+catalog" in combined
    assert "https://download.example/course" not in combined
    assert message.markups[0].inline_keyboard[0][0].text == "Замовити"


@pytest.mark.asyncio
async def test_course_deep_link_shows_download_for_paid_user() -> None:
    message = FakeMessage("/start course_stable-course")
    bot_users = FakeBotUserRepository()
    localization = LocalizationService(FakeLanguageRepository())

    await handle_start(
        message,
        bot_users,
        localization,
        FakeCatalogService(),
        FakeOrderService(paid=True),
    )

    combined = "\n".join(message.answers)
    assert "Stable Course" in combined
    assert "https://download.example/course" in combined
    assert "https://t.me/+catalog" in combined


@pytest.mark.asyncio
async def test_unmarked_channel_posts_are_not_copied_to_unpaid_user() -> None:
    message = FakeMessage("/start course_stable-course")
    copied: list[int] = []

    class FakeBot:
        async def copy_message(self, *, chat_id: int, from_chat_id: int, message_id: int) -> None:
            copied.append(message_id)

    message.bot = FakeBot()

    await handle_start(
        message,
        FakeBotUserRepository(),
        LocalizationService(FakeLanguageRepository()),
        FakeCatalogService(),
        FakeOrderService(paid=False),
    )

    assert copied == []
    assert "https://download.example/course" not in "\n".join(message.answers)
