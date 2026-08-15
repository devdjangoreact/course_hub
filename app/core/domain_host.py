from urllib.parse import urlparse


def normalize_bot_username(raw: str) -> str:
    return raw.lstrip("@").strip().lower()


def hostname_from_url(url: str) -> str:
    netloc = urlparse(url).netloc
    if not netloc:
        return ""
    host, _, _ = netloc.partition(":")
    return host


def host_from_headers(*, host: str, forwarded_host: str = "") -> str:
    first = (forwarded_host or "").split(",")[0].strip()
    return first or (host or "").strip()


def _host_without_port(host: str) -> str:
    host = host.strip()
    if host.startswith("["):
        end = host.find("]")
        if end != -1:
            return host[: end + 1]
        return host
    return host.partition(":")[0]


def bot_username_from_host(host: str, base_domain: str) -> str | None:
    host = _host_without_port(host.lower())
    base_domain = base_domain.lower().strip()
    if not host or not base_domain:
        return None
    if host == base_domain or host == f"www.{base_domain}":
        return None
    suffix = f".{base_domain}"
    if not host.endswith(suffix):
        return None
    username = host[: -len(suffix)]
    if not username:
        return None
    # Telegram usernames allow `_` not `-`; CF/Vercel TLS often rejects `_` in the label.
    return username.replace("-", "_")


def resolve_base_domain(*, base_domain: str, backend_url: str) -> str:
    explicit = base_domain.strip()
    if explicit:
        return explicit
    return hostname_from_url(backend_url)


def webhook_url_for_bot(*, username: str, base_domain: str, webhook_path: str) -> str:
    label = normalize_bot_username(username).replace("_", "-")
    return f"https://{label}.{base_domain}{webhook_path}"
