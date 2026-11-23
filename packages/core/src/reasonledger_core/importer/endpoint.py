"""Where a model call goes: validate a configured base URL and name its origin.

A prompt carries repo text and the request carries an API key, so the address they go to is
checked before anything is sent. A model on this machine (a loopback host) may use plain HTTP;
any other address must use HTTPS. Credentials and secrets never belong in the URL itself, which
is committed in ``.reasonledger/config.yml``, so a URL with userinfo, a query or a fragment is
refused. Consent is bound to the origin (scheme, host and port), not the host alone, so moving
a repo from HTTPS to HTTP, or to another port, asks again.
"""

from __future__ import annotations

from urllib.parse import urlsplit

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
SECURE_SCHEME = "https"
LOOPBACK_ONLY_SCHEME = "http"
DEFAULT_PORTS = {"http": 80, "https": 443}


class EndpointError(ValueError):
    """A base URL a model call must not be sent to."""


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def is_loopback(base_url: str | None) -> bool:
    host = _host(base_url or "")
    return host in LOOPBACK_HOSTS or host.endswith(".localhost")


def validate_base_url(url: str) -> str:
    """``url`` unchanged when a model call may go there; raises EndpointError otherwise."""
    try:
        parts = urlsplit(url)
        origin(url)  # reads the port, so a malformed one is refused here, not at call time
    except ValueError as exc:
        raise EndpointError(f"base_url is not a valid URL: {exc}") from exc
    if parts.scheme not in DEFAULT_PORTS or not parts.hostname:
        raise EndpointError("base_url must be an http(s) URL with a host")
    if parts.username is not None or parts.password is not None:
        raise EndpointError("base_url must not carry a user name or password; use api_key_env")
    if parts.query or parts.fragment:
        raise EndpointError("base_url must not carry a query or fragment; use api_key_env")
    if parts.scheme == LOOPBACK_ONLY_SCHEME and not is_loopback(url):
        raise EndpointError(
            "base_url uses http, which sends prompts and the API key in clear text; use https, or "
            "http only for a model on this machine (localhost)"
        )
    return url


def origin(url: str) -> str:
    """``scheme://host[:port]``, lowercase, with the scheme's default port left out."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = _host(url)
    shown = f"[{host}]" if ":" in host else host
    port = parts.port
    if port is None or port == DEFAULT_PORTS.get(scheme):
        return f"{scheme}://{shown}"
    return f"{scheme}://{shown}:{port}"
