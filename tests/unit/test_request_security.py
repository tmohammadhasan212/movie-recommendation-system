from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.app.core.request_security import require_same_origin


def request(
    *, host: str = "app.example", request_scheme: str = "https", **headers: str
) -> Request:
    raw_headers = [(b"host", host.encode())]
    raw_headers.extend((name.replace("_", "-").encode(), value.encode()) for name, value in headers.items())
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": request_scheme,
            "server": ("app.example", 443),
            "path": "/api/v1/me",
            "query_string": b"",
            "headers": raw_headers,
        }
    )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"origin": "https://app.example"},
        {"referer": "https://app.example/account"},
        {"origin": "https://app.example:443"},
        {"sec_fetch_site": "same-origin", "origin": "https://app.example"},
        {
            "request_scheme": "http",
            "x_forwarded_proto": "https",
            "origin": "https://app.example",
        },
        {
            "host": "api:8000",
            "request_scheme": "http",
            "x_forwarded_host": "app.example:5173",
            "x_forwarded_proto": "http",
            "origin": "http://app.example:5173",
        },
    ],
)
def test_same_origin_and_non_browser_requests_are_allowed(headers: dict[str, str]) -> None:
    require_same_origin(request(**headers))


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://evil.example"},
        {"origin": "http://app.example"},
        {"origin": "null"},
        {"referer": "https://evil.example/account"},
        {"origin": "https://app.example:8443"},
        {"origin": "https://user@app.example"},
        {"sec_fetch_site": "cross-site"},
    ],
)
def test_cross_origin_browser_requests_are_rejected(headers: dict[str, str]) -> None:
    with pytest.raises(HTTPException) as captured:
        require_same_origin(request(**headers))

    assert captured.value.status_code == 403
    assert captured.value.detail == "Cross-origin request rejected"
