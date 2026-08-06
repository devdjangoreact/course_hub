import importlib
import json
import sys
from types import SimpleNamespace

import pytest

from app.domain.entities.parser_source import ParserSource
from app.infrastructure.parsers.catalog_parser import HttpCatalogParser


@pytest.mark.asyncio
async def test_inactive_source_returns_safe_error() -> None:
    parser = HttpCatalogParser()

    result = await parser.parse(
        ParserSource(
            id=1,
            name="Example",
            source_type="html",
            url="https://example.com",
            is_active=False,
        )
    )

    assert result.errors == ["Source is inactive"]


def _catalog_tool(monkeypatch: pytest.MonkeyPatch, name: str, config: object):
    monkeypatch.syspath_prepend("tools/catalog")
    monkeypatch.setitem(sys.modules, "config", config)
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def test_channel_posts_hide_download_and_have_order_buttons(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(
        BOT_TOKEN="test",
        CATALOG_CHANNEL_ID=-1001,
        CATALOG_DISCUSSION_GROUP_ID=None,
        CATALOG_INVITE_LINK="",
    )
    post_channel = _catalog_tool(monkeypatch, "post_channel", config)
    path = tmp_path / "course.json"
    download = "https://cloud.mail.ru/private"
    path.write_text(
        json.dumps(
            {
                "slug": "stable-course",
                "promo": {"text": f"Promo\n{download}"},
                "full_description": f"Full\n{download}",
                "download_link": download,
                "telegram": {},
            }
        ),
        encoding="utf-8",
    )
    payloads: list[dict[str, object]] = []

    def bot_call(method: str, payload: dict[str, object]) -> dict[str, int]:
        assert method == "sendMessage"
        payloads.append(payload)
        return {"message_id": len(payloads)}

    monkeypatch.setattr(post_channel, "_bot_call", bot_call)

    post_channel.post_course(path, bot_username="course_hub_bot")

    assert len(payloads) == 2
    for payload in payloads:
        assert download not in str(payload["text"])
        button = payload["reply_markup"]["inline_keyboard"][0][0]
        assert button["text"] == "Замовити"
        assert button["url"] == ("https://t.me/course_hub_bot?start=course_stable-course")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert download not in saved["promo"]["text"]
    assert download not in saved["full_description"]
    assert saved["telegram"]["public_text_sanitized"] is True


def test_channel_posting_resolves_bot_username_once(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(
        BOT_TOKEN="test",
        CATALOG_ROOT=tmp_path,
        CATALOG_CHANNEL_ID=-1001,
        CATALOG_DISCUSSION_GROUP_ID=None,
        CATALOG_INVITE_LINK="",
    )
    post_channel = _catalog_tool(monkeypatch, "post_channel", config)
    path = tmp_path / "course.json"
    path.write_text("{}", encoding="utf-8")
    usernames: list[str] = []
    monkeypatch.setattr(
        post_channel,
        "_bot_call",
        lambda method, payload: {"username": "course_hub_bot"},
    )
    monkeypatch.setattr(
        post_channel,
        "select_course_json_files",
        lambda *args, **kwargs: [path],
    )
    monkeypatch.setattr(
        post_channel,
        "post_course",
        lambda path, *, bot_username, force: usernames.append(bot_username) or True,
    )

    assert post_channel.post_all() == 1
    assert usernames == ["course_hub_bot"]


def test_existing_channel_posts_are_sanitized_without_reposting(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(
        BOT_TOKEN="test",
        CATALOG_CHANNEL_ID=-1001,
        CATALOG_DISCUSSION_GROUP_ID=None,
        CATALOG_INVITE_LINK="",
    )
    post_channel = _catalog_tool(monkeypatch, "post_channel", config)
    path = tmp_path / "course.json"
    download = "https://cloud.mail.ru/private"
    path.write_text(
        json.dumps(
            {
                "slug": "stable-course",
                "promo": {"text": f"Promo\n{download}"},
                "full_description": f"Full\n{download}",
                "download_link": download,
                "telegram": {
                    "promo_message_ids": [10],
                    "full_message_ids": [11],
                },
            }
        ),
        encoding="utf-8",
    )
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        post_channel,
        "_bot_call",
        lambda method, payload: calls.append((method, payload)) or {},
    )

    assert not post_channel.post_course(path, bot_username="course_hub_bot")

    assert [method for method, _ in calls] == ["editMessageText", "editMessageText"]
    assert {payload["message_id"] for _, payload in calls} == {10, 11}
    for _, payload in calls:
        assert download not in str(payload["text"])
        assert payload["reply_markup"]["inline_keyboard"][0][0]["text"] == "Замовити"


def test_unchanged_channel_post_update_is_idempotent(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(
        BOT_TOKEN="test",
        CATALOG_CHANNEL_ID=-1001,
        CATALOG_DISCUSSION_GROUP_ID=None,
        CATALOG_INVITE_LINK="",
    )
    post_channel = _catalog_tool(monkeypatch, "post_channel", config)
    path = tmp_path / "course.json"
    path.write_text(
        json.dumps(
            {
                "slug": "stable-course",
                "promo": {"text": "Promo"},
                "full_description": "Full",
                "download_link": "https://download.example/private",
                "telegram": {
                    "promo_message_ids": [10],
                    "full_message_ids": [11],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        post_channel,
        "_bot_call",
        lambda method, payload: (_ for _ in ()).throw(
            RuntimeError("Telegram Bot API editMessageText failed: message is not modified")
        ),
    )

    assert not post_channel.post_course(path, bot_username="course_hub_bot")


def test_partial_channel_post_saves_sent_message_id(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SimpleNamespace(
        BOT_TOKEN="test",
        CATALOG_CHANNEL_ID=-1001,
        CATALOG_DISCUSSION_GROUP_ID=None,
        CATALOG_INVITE_LINK="",
    )
    post_channel = _catalog_tool(monkeypatch, "post_channel", config)
    path = tmp_path / "course.json"
    path.write_text(
        json.dumps(
            {
                "slug": "stable-course",
                "promo": {"text": "Promo"},
                "full_description": "Full",
                "download_link": "https://download.example/private",
                "telegram": {},
            }
        ),
        encoding="utf-8",
    )
    calls = 0

    def bot_call(method: str, payload: dict[str, object]) -> dict[str, int]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"message_id": 10}
        raise RuntimeError("full post failed")

    monkeypatch.setattr(post_channel, "_bot_call", bot_call)

    with pytest.raises(RuntimeError, match="full post failed"):
        post_channel.post_course(path, bot_username="course_hub_bot")

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["telegram"]["promo_message_ids"] == [10]
    assert saved["telegram"]["full_message_ids"] == []


def test_force_repost_appends_new_message_ids(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(
        BOT_TOKEN="test",
        CATALOG_CHANNEL_ID=-1001,
        CATALOG_DISCUSSION_GROUP_ID=None,
        CATALOG_INVITE_LINK="",
    )
    post_channel = _catalog_tool(monkeypatch, "post_channel", config)
    path = tmp_path / "course.json"
    path.write_text(
        json.dumps(
            {
                "slug": "stable-course",
                "promo": {"text": "Promo"},
                "full_description": "Full",
                "download_link": "https://download.example/private",
                "telegram": {
                    "promo_message_ids": [10],
                    "full_message_ids": [11],
                },
            }
        ),
        encoding="utf-8",
    )
    ids = iter((20, 21))
    methods: list[str] = []

    def bot_call(method: str, payload: dict[str, object]) -> dict[str, int]:
        methods.append(method)
        return {"message_id": next(ids)}

    monkeypatch.setattr(post_channel, "_bot_call", bot_call)

    assert post_channel.post_course(path, bot_username="course_hub_bot", force=True)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert methods == ["sendMessage", "sendMessage"]
    assert saved["telegram"]["promo_message_ids"] == [10, 20]
    assert saved["telegram"]["full_message_ids"] == [11, 21]


def test_normalize_preserves_metadata_and_cleans_public_text(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog_root = tmp_path / "catalog"
    category_dir = catalog_root / "categories" / "flancki_need_enrich"
    category_dir.mkdir(parents=True)
    export_path = tmp_path / "posts.json"
    download = "https://cloud.mail.ru/private"
    export_path.write_text(
        json.dumps(
            [
                {
                    "id": 1,
                    "chat_id": 123,
                    "date": "2026-07-29T10:00:00",
                    "courses": [{"title": "Stable Course", "link": download}],
                }
            ]
        ),
        encoding="utf-8",
    )
    course_path = category_dir / "2026-07-29_1_01.json"
    course_path.write_text(
        json.dumps(
            {
                "promo": {"text": f"Curated promo\n{download}", "media": []},
                "full_description": f"Curated full\n{download}",
                "short_description": f"Curated short\n{download}",
                "telegram": {
                    "promo_message_ids": [10],
                    "full_message_ids": [11],
                },
                "custom_metadata": {"keep": True},
            }
        ),
        encoding="utf-8",
    )
    normalize = _catalog_tool(
        monkeypatch,
        "normalize",
        SimpleNamespace(TG_FLANCKI_CHAT_ID=123, CATALOG_ROOT=catalog_root),
    )

    normalize.normalize_flancki_export(export_path)

    data = json.loads(course_path.read_text(encoding="utf-8"))
    assert download not in data["promo"]["text"]
    assert download not in data["full_description"]
    assert download not in data["short_description"]
    assert data["download_link"] == download
    assert data["telegram"]["promo_message_ids"] == [10]
    assert data["telegram"]["full_message_ids"] == [11]
    assert data["custom_metadata"] == {"keep": True}


def test_pipeline_syncs_then_posts_the_same_selected_courses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_pipeline = _catalog_tool(
        monkeypatch, "run_pipeline", SimpleNamespace(CATALOG_ROOT=object())
    )
    selected = [SimpleNamespace(name="one.json"), SimpleNamespace(name="two.json")]
    calls: list[tuple[str, object]] = []

    monkeypatch.setitem(
        sys.modules,
        "course_json",
        SimpleNamespace(select_course_json_files=lambda *args, **kwargs: selected),
    )
    monkeypatch.setitem(
        sys.modules,
        "normalize",
        SimpleNamespace(
            normalize_flancki_export=lambda **kwargs: calls.append(("normalize", None))
        ),
    )

    async def sync_main(**kwargs) -> int:
        calls.append(("sync", kwargs["paths"]))
        return len(kwargs["paths"])

    monkeypatch.setitem(sys.modules, "sync_db", SimpleNamespace(main=sync_main))
    monkeypatch.setitem(
        sys.modules,
        "post_channel",
        SimpleNamespace(post_all=lambda **kwargs: calls.append(("post", kwargs["paths"]))),
    )

    run_pipeline.run_pipeline(normalize=True, sync_db=True, post=True, course_limit=2)

    assert calls == [
        ("normalize", None),
        ("sync", selected),
        ("post", selected),
        ("sync", selected),
    ]
