from dataclasses import replace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.application.services.runtime_settings import load_runtime_settings
from app.bot.registry import BotRegistry, RegisteredBot


class _FakeAiogramBot:
    pass


class _RecordingBotApp:
    def __init__(self) -> None:
        self.registry = BotRegistry()
        self.calls: list[str] = []

    async def handle_update(self, update, *, registered: RegisteredBot) -> None:  # noqa: ANN001
        self.calls.append(registered.username)


async def test_webhook_routes_by_host(app: FastAPI, monkeypatch) -> None:
    monkeypatch.setenv("BASE_DOMAIN", "example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    app.state.settings = settings
    async with app.state.db.session_factory() as session:
        runtime = await load_runtime_settings(session, settings)
    app.state.runtime_settings = replace(runtime, base_domain="example.com")

    fake = _RecordingBotApp()
    fake.registry.upsert(
        RegisteredBot(
            bot_id=1,
            username="alpha",
            token="t1",
            webhook_secret="",
            aiogram_bot=_FakeAiogramBot(),  # type: ignore[arg-type]
        )
    )
    fake.registry.upsert(
        RegisteredBot(
            bot_id=2,
            username="beta",
            token="t2",
            webhook_secret="secret-beta",
            aiogram_bot=_FakeAiogramBot(),  # type: ignore[arg-type]
        )
    )
    app.state.bot_app = fake  # type: ignore[assignment]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.post(
            "/api/telegram/webhook",
            headers={"host": "alpha.example.com"},
            json={"update_id": 1},
        )
        assert ok.status_code == 200
        assert fake.calls == ["alpha"]

        missing = await client.post(
            "/api/telegram/webhook",
            headers={"host": "unknown.example.com"},
            json={"update_id": 2},
        )
        assert missing.status_code == 404

        bad_secret = await client.post(
            "/api/telegram/webhook",
            headers={
                "host": "beta.example.com",
                "x-telegram-bot-api-secret-token": "wrong",
            },
            json={"update_id": 3},
        )
        assert bad_secret.status_code == 401

        good_secret = await client.post(
            "/api/telegram/webhook",
            headers={
                "host": "beta.example.com",
                "x-telegram-bot-api-secret-token": "secret-beta",
            },
            json={"update_id": 4},
        )
        assert good_secret.status_code == 200
        assert fake.calls == ["alpha", "beta"]

        forwarded = await client.post(
            "/api/telegram/webhook",
            headers={"host": "ignored.vercel.app", "x-forwarded-host": "alpha.example.com"},
            json={"update_id": 5},
        )
        assert forwarded.status_code == 200
        assert fake.calls == ["alpha", "beta", "alpha"]


async def test_webhook_falls_back_to_single_bot_on_apex_host(app: FastAPI, monkeypatch) -> None:
    monkeypatch.setenv("BASE_DOMAIN", "example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    app.state.settings = settings
    async with app.state.db.session_factory() as session:
        runtime = await load_runtime_settings(session, settings)
    app.state.runtime_settings = replace(runtime, base_domain="example.com")

    fake = _RecordingBotApp()
    fake.registry.upsert(
        RegisteredBot(
            bot_id=1,
            username="onlybot",
            token="t1",
            webhook_secret="",
            aiogram_bot=_FakeAiogramBot(),  # type: ignore[arg-type]
        )
    )
    app.state.bot_app = fake  # type: ignore[assignment]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.post(
            "/api/telegram/webhook",
            headers={"host": "example.com"},
            json={
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "date": 1,
                    "chat": {"id": 1, "type": "private"},
                    "from": {"id": 1, "is_bot": False, "first_name": "A"},
                    "text": "/start",
                },
            },
        )
        assert ok.status_code == 200
        assert fake.calls == ["onlybot"]
