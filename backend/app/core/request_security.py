"""Browser request provenance checks used alongside session CSRF tokens."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request


def _default_port(scheme: str) -> int | None:
    return {"http": 80, "https": 443}.get(scheme.casefold())


def _same_authority(request: Request, source: str) -> bool:
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",", 1)[0].strip()
    target_authority = forwarded_host or request.headers.get("host", "")
    try:
        parsed = urlsplit(source)
        target = urlsplit(f"//{target_authority}")
        source_port = parsed.port
        target_port = target.port
    except ValueError:
        return False
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    if not target.hostname or target.username or target.password:
        return False
    if parsed.hostname.casefold() != target.hostname.casefold():
        return False

    forwarded_scheme = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().casefold()
    target_scheme = forwarded_scheme if forwarded_scheme in {"http", "https"} else request.url.scheme.casefold()
    if parsed.scheme.casefold() != target_scheme:
        return False

    source_effective_port = source_port or _default_port(parsed.scheme)
    target_effective_port = target_port or _default_port(target_scheme)
    return source_effective_port == target_effective_port


def require_same_origin(request: Request) -> None:
    """Reject browser-proven cross-origin requests before state is accessed."""
    if request.headers.get("sec-fetch-site", "").casefold() == "cross-site":
        raise HTTPException(403, "Cross-origin request rejected")

    source = request.headers.get("origin") or request.headers.get("referer")
    if source is not None and not _same_authority(request, source):
        raise HTTPException(403, "Cross-origin request rejected")
