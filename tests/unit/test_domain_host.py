from app.core.domain_host import (
    bot_username_from_host,
    normalize_bot_username,
    resolve_base_domain,
    webhook_url_for_bot,
)


def test_normalize_bot_username() -> None:
    assert normalize_bot_username("@MyBot") == "mybot"


def test_bot_username_from_host() -> None:
    assert bot_username_from_host("shop.example.com", "example.com") == "shop"
    assert bot_username_from_host("example.com", "example.com") is None
    assert bot_username_from_host("www.example.com", "example.com") is None
    assert bot_username_from_host("shop.other.com", "example.com") is None


def test_bot_username_from_host_strips_port() -> None:
    assert bot_username_from_host("shop.example.com:443", "example.com") == "shop"
    assert bot_username_from_host("Shop.Example.Com:8080", "example.com") == "shop"


def test_resolve_base_domain_prefers_explicit() -> None:
    assert resolve_base_domain(base_domain="bots.example.com", backend_url="https://api.example.com") == "bots.example.com"
    assert resolve_base_domain(base_domain="", backend_url="https://api.example.com:443/") == "api.example.com"


def test_webhook_url_for_bot() -> None:
    assert (
        webhook_url_for_bot(username="shop", base_domain="example.com", webhook_path="/api/telegram/webhook")
        == "https://shop.example.com/api/telegram/webhook"
    )
