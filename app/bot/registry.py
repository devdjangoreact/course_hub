from contextvars import ContextVar, Token
from dataclasses import dataclass

from aiogram import Bot

from app.core.domain_host import normalize_bot_username

_hub_bot_id: ContextVar[int | None] = ContextVar("hub_bot_id", default=None)


def set_hub_bot_id(bot_id: int | None) -> Token:
    return _hub_bot_id.set(bot_id)


def get_hub_bot_id() -> int | None:
    return _hub_bot_id.get()


def reset_hub_bot_id(token: Token) -> None:
    _hub_bot_id.reset(token)


@dataclass(slots=True)
class RegisteredBot:
    bot_id: int
    username: str
    token: str
    webhook_secret: str
    aiogram_bot: Bot


class BotRegistry:
    def __init__(self) -> None:
        self._by_username: dict[str, RegisteredBot] = {}
        self._by_id: dict[int, RegisteredBot] = {}

    def get(self, username: str) -> RegisteredBot | None:
        return self._by_username.get(normalize_bot_username(username))

    def get_by_id(self, bot_id: int) -> RegisteredBot | None:
        return self._by_id.get(bot_id)

    def all_active(self) -> list[RegisteredBot]:
        return list(self._by_username.values())

    def replace_all(self, entries: list[RegisteredBot]) -> None:
        self._by_username.clear()
        self._by_id.clear()
        for entry in entries:
            self.upsert(entry)

    def upsert(self, entry: RegisteredBot) -> None:
        old = self._by_id.get(entry.bot_id)
        if old is not None:
            old_key = normalize_bot_username(old.username)
            if old_key != normalize_bot_username(entry.username):
                self._by_username.pop(old_key, None)
        key = normalize_bot_username(entry.username)
        self._by_username[key] = entry
        self._by_id[entry.bot_id] = entry

    def remove(self, username: str) -> None:
        key = normalize_bot_username(username)
        entry = self._by_username.pop(key, None)
        if entry is not None:
            self._by_id.pop(entry.bot_id, None)
