from fastapi import FastAPI
from httpx import AsyncClient

from app.application.services.runtime_settings import load_runtime_settings
from app.bot.context import BotRuntime
from app.bot.keyboards.catalog import course_detail_keyboard
from app.bot.registry import RegisteredBot
from app.bot.runner import BotApp
from app.infrastructure.db.repositories.course_repository import SqlCourseRepository


def test_course_detail_keyboard_uses_localized_actions() -> None:
    markup = course_detail_keyboard(1, "uk")

    assert markup.inline_keyboard[0][0].text == "Замовити"
    assert markup.inline_keyboard[0][0].callback_data == "order:1"
    assert markup.inline_keyboard[-1][0].text == "Меню"
    assert [button.callback_data for row in markup.inline_keyboard for button in row] == [
        "order:1",
        "menu:home",
    ]


async def test_payment_notification_only_delivers_access_for_paid_status(
    app: FastAPI, client: AsyncClient, seeded: dict[str, int], monkeypatch
) -> None:
    download = "https://download.example/paid-course"
    invite = "https://t.me/+catalog"
    async with app.state.db.session_factory() as session:
        courses = SqlCourseRepository(session)
        course = await courses.get(seeded["course_id"])
        assert course is not None
        course.extra = {"download_link": download, "invite_link": invite}
        await courses.update(course)
        await session.commit()

    created = await client.post(
        "/api/orders",
        json={"telegram_id": 777, "course_id": seeded["course_id"]},
    )
    body = created.json()
    await client.post(
        "/api/payments/simulate",
        params={
            "reference": body["payment"]["payment_reference"],
            "result": "succeeded",
        },
    )
    messages: list[str] = []

    class _FakeSession:
        async def close(self) -> None:
            return None

    class FakeBot:
        def __init__(self) -> None:
            self.session = _FakeSession()

        async def send_message(self, telegram_id: int, text: str) -> None:
            assert telegram_id == 777
            messages.append(text)

    monkeypatch.setattr("app.bot.runner._make_bot", lambda token, force_close=True: FakeBot())

    async with app.state.db.session_factory() as session:
        runtime_settings = await load_runtime_settings(session, app.state.settings)
    bot_app = BotApp(
        BotRuntime(
            database=app.state.db,
            env_settings=app.state.settings,
            rate_limiter=app.state.rate_limiter,
            payment_gateway=app.state.payment_gateway,
            runtime_settings=runtime_settings,
        )
    )
    bot_app.registry.upsert(
        RegisteredBot(
            bot_id=1,
            username="testbot",
            token="123456:AACtesttokenfortestsxxxxxx",
            webhook_secret="",
            aiogram_bot=FakeBot(),  # type: ignore[arg-type]
        )
    )

    await bot_app.notify_payment_status(777, body["order_id"], "paid")
    paid_text = "\n".join(messages)
    assert download in paid_text
    assert invite in paid_text

    for status in ("failed", "cancelled"):
        messages.clear()
        await bot_app.notify_payment_status(777, body["order_id"], status)
        status_text = "\n".join(messages)
        assert download not in status_text
        assert invite not in status_text
