from decimal import Decimal

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from app.application.errors import NotFoundError, RateLimitedError, ValidationError
from app.application.services.catalog_service import LocalizedCategory, LocalizedCourse
from app.application.services.localization_service import LocalizationService
from app.bot.handlers.categories import show_categories, show_course, show_courses
from app.bot.handlers.order import create_order
from app.bot.handlers.search import prompt_search, run_search
from app.bot.handlers.start import (
    handle_help,
    handle_home,
    handle_language_menu,
    handle_language_selected,
    handle_start,
)
from app.bot.states import SearchStates
from app.domain.entities.bot_user import BotUser
from app.domain.entities.order import Order
from app.domain.entities.order_status import OrderStatus
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.repositories.bot_user_repository import BotUserRepository
from app.domain.repositories.suggestion_search_repository import SearchSuggestion
from tests.unit.test_localization_service import FakeLanguageRepository


class FakeTelegramUser:
    id = 42
    username = "nav"
    full_name = "Nav User"


class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.from_user = FakeTelegramUser()
        self.text = text
        self.bot = None
        self.answers: list[str] = []
        self.edits: list[str] = []
        self.markups: list[object | None] = []

    async def answer(self, text: str, reply_markup: object | None = None, **kwargs: object) -> None:
        del kwargs
        self.answers.append(text)
        self.markups.append(reply_markup)

    async def edit_text(
        self, text: str, reply_markup: object | None = None, **kwargs: object
    ) -> None:
        del kwargs
        self.edits.append(text)
        self.markups.append(reply_markup)


class FakeCallback:
    def __init__(self, data: str, message: FakeMessage) -> None:
        self.data = data
        self.from_user = FakeTelegramUser()
        self.message = message
        self.bot = None
        self.alerts: list[str | None] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        del show_alert
        self.alerts.append(text)


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


class FakeCatalog:
    def __init__(self) -> None:
        self.category = LocalizedCategory(
            id=1, name="Programming", language="ru", fallback_used=False
        )
        self.course = LocalizedCourse(
            id=7,
            name="Async FastAPI",
            description="Build APIs.",
            category_id=1,
            price=Decimal("79.00"),
            link="https://example.com/fastapi",
            language="ru",
            fallback_used=False,
            extra={"invite_link": "https://t.me/+catalog", "download_link": "https://dl.example/c"},
        )

    async def list_localized_categories(self, language: str) -> list[LocalizedCategory]:
        del language
        return [self.category]

    async def list_localized_courses(
        self, category_id: int, language: str
    ) -> list[LocalizedCourse]:
        del language
        if category_id != 1:
            raise NotFoundError("Category not found")
        return [self.course]

    async def get_localized_course(self, course_id: int, language: str) -> LocalizedCourse:
        del language
        if course_id != 7:
            raise NotFoundError("Course not found")
        return self.course


class FakeOrders:
    def __init__(self, provider: str = "simulated") -> None:
        self.provider = provider
        self.paid = False

    async def has_paid_course(self, telegram_id: int, course_id: int) -> bool:
        del telegram_id, course_id
        return self.paid

    async def uses_lava_provider(self) -> bool:
        return self.provider == "lava"

    async def uses_atlos_provider(self) -> bool:
        return self.provider == "atlos"

    async def payment_link_mode(self) -> str:
        return "direct"

    async def payment_currency(self) -> str:
        return "USD"

    async def create_order(self, **kwargs: object) -> tuple[Order, PaymentIntent]:
        del kwargs
        order = Order(
            id=9,
            bot_user_id=1,
            course_id=7,
            amount=Decimal("79.00"),
            status=OrderStatus.PENDING,
        )
        if self.provider == "atlos":
            intent = PaymentIntent("atlos-9-deadbeef", "pay", "https://atlos.io/payment/inv1")
        else:
            intent = PaymentIntent(
                "sim_abc",
                "pay",
                "https://hub.example/api/payments/simulate?reference=sim_abc&result=succeeded",
            )
        return order, intent


class FakeRuntime:
    backend_url = "https://hub.example"


class FakeSearch:
    def __init__(
        self, suggestions: list[SearchSuggestion] | None = None, error: Exception | None = None
    ) -> None:
        self.suggestions = suggestions or []
        self.error = error

    async def suggest(self, query: str, language: str, rate_key: str) -> list[SearchSuggestion]:
        del query, language, rate_key
        if self.error is not None:
            raise self.error
        return self.suggestions


def _fsm() -> FSMContext:
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=42, user_id=42))


def _callbacks(markup: object) -> list[str]:
    rows = getattr(markup, "inline_keyboard", [])
    return [button.callback_data for row in rows for button in row]


@pytest.fixture
def nav() -> tuple[FakeBotUserRepository, LocalizationService, FakeCatalog, FakeMessage]:
    users = FakeBotUserRepository()
    return users, LocalizationService(FakeLanguageRepository()), FakeCatalog(), FakeMessage()


@pytest.mark.asyncio
async def test_start_help_language_and_home_navigation(nav: tuple) -> None:
    users, localization, _catalog, message = nav
    await handle_start(message, users, localization)
    assert "Выберите язык" in message.answers[0]
    assert _callbacks(message.markups[0]) == ["language:ru", "language:uk", "language:en"]

    callback = FakeCallback("language:uk", message)
    await handle_language_selected(callback, users, localization)
    assert users.users[42].preferred_language == "uk"
    assert "Мову збережено" in message.edits[0] or "Language saved" in message.edits[0]
    assert _callbacks(message.markups[-1]) == ["menu:categories", "menu:search", "menu:language"]

    home = FakeCallback("menu:home", message)
    await handle_home(home, users, localization)
    assert _callbacks(message.markups[-1]) == ["menu:categories", "menu:search", "menu:language"]

    lang_menu = FakeCallback("menu:language", message)
    await handle_language_menu(lang_menu, localization)
    assert _callbacks(message.markups[-1]) == ["language:ru", "language:uk", "language:en"]

    help_msg = FakeMessage("/help")
    await handle_help(help_msg, users, localization)
    assert _callbacks(help_msg.markups[0]) == ["menu:categories", "menu:search", "menu:language"]


@pytest.mark.asyncio
async def test_categories_courses_course_and_back_to_menu(nav: tuple) -> None:
    users, localization, catalog, message = nav
    await users.upsert(BotUser(id=None, telegram_id=42, username="nav", preferred_language="uk"))
    orders = FakeOrders()

    await show_categories(FakeCallback("menu:categories", message), catalog, users, localization)
    assert _callbacks(message.markups[-1]) == ["cat:1", "menu:home"]

    await show_courses(FakeCallback("cat:1", message), catalog, users, localization)
    assert _callbacks(message.markups[-1]) == ["course:7", "menu:categories"]

    await show_course(FakeCallback("course:7", message), catalog, orders, users, localization)
    assert "Async FastAPI" in message.edits[-1]
    assert "https://t.me/+catalog" in message.edits[-1]
    assert "https://dl.example/c" not in message.edits[-1]
    assert _callbacks(message.markups[-1]) == ["order:7", "menu:home"]

    await handle_home(FakeCallback("menu:home", message), users, localization)
    assert _callbacks(message.markups[-1]) == ["menu:categories", "menu:search", "menu:language"]


@pytest.mark.asyncio
async def test_search_query_suggestions_and_open_course(nav: tuple) -> None:
    users, localization, catalog, message = nav
    await users.upsert(BotUser(id=None, telegram_id=42, username="nav", preferred_language="en"))
    state = _fsm()
    await prompt_search(FakeCallback("menu:search", message), state, users, localization)
    assert await state.get_state() == SearchStates.awaiting_query.state
    assert "Send a search term:" in message.edits[-1]

    query = FakeMessage("fastapi")
    await run_search(
        query,
        state,
        FakeSearch(
            [SearchSuggestion(type="course", id=7, title="Async FastAPI", subtitle=None, score=1.0)]
        ),
        users,
        localization,
    )
    assert _callbacks(query.markups[-1]) == ["course:7", "menu:search", "menu:home"]

    await show_course(FakeCallback("course:7", message), catalog, FakeOrders(), users, localization)
    assert _callbacks(message.markups[-1]) == ["order:7", "menu:home"]

    empty = FakeMessage("zzz")
    await run_search(empty, _fsm(), FakeSearch([]), users, localization)
    assert "No results" in empty.answers[0]

    short = FakeMessage("ab")
    await run_search(short, _fsm(), FakeSearch(error=ValidationError("short")), users, localization)
    assert "at least 3" in short.answers[0].lower() or "не менее 3" in short.answers[0]

    limited = FakeMessage("fastapi")
    await run_search(
        limited, _fsm(), FakeSearch(error=RateLimitedError("slow")), users, localization
    )
    assert "Too many" in limited.answers[0] or "Слишком" in limited.answers[0]


@pytest.mark.asyncio
async def test_simulated_and_atlos_order_pay_buttons(nav: tuple) -> None:
    users, localization, catalog, message = nav
    await users.upsert(BotUser(id=None, telegram_id=42, username="nav", preferred_language="uk"))

    sim = FakeCallback("order:7", message)
    await create_order(
        sim, _fsm(), FakeOrders("simulated"), catalog, FakeRuntime(), users, localization
    )
    assert "Тестова оплата" in message.answers[-1]
    assert (
        message.markups[-1]
        .inline_keyboard[0][0]
        .url.endswith("/api/payments/simulate?reference=sim_abc&result=succeeded")
    )

    atlos = FakeCallback("order:7", message)
    await create_order(
        atlos, _fsm(), FakeOrders("atlos"), catalog, FakeRuntime(), users, localization
    )
    assert "atlos.io" in message.answers[-1]
    assert message.markups[-1].inline_keyboard[0][0].url == "https://atlos.io/payment/inv1"
