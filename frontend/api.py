"""Every HTTP call to the backend lives here. The UI never sees httpx."""

import os
from typing import Any, TypedDict

import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TIMEOUT = httpx.Timeout(10.0, connect=2.0)
AI_TIMEOUT = httpx.Timeout(100.0, connect=2.0)  # covers the backend's AI retries
NOT_SENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.UnsupportedProtocol)


class Item(TypedDict):
    """One item as the backend returns it (ItemPublic)."""

    id: int
    title: str
    description: str
    priority: int
    tags: str


class BackendError(Exception):
    """Something went wrong; str(error) is a message you can show to a user."""


class BackendUnavailable(BackendError):
    """Nothing reached the backend (refused, DNS, connect timeout): safe to retry."""


class BackendNoAnswer(BackendError):
    """The request was sent but no full reply came back in time: outcome unknown."""


def _friendly(response: httpx.Response) -> str:
    match response.status_code:
        case 422:
            problems = [
                f"{err['loc'][-1]}: {err['msg']}" for err in response.json()["detail"]
            ]
            return "Please fix: " + "; ".join(problems)
        case 404:
            return "That item no longer exists. Reload the page."
        case 503:
            return "AI service is unavailable, try again in a minute."
        case 502:
            return "AI returned something unusable. Try rewording the text."
        case code:
            return f"The backend failed ({code}). Check its logs."


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", TIMEOUT)
    try:
        response = httpx.request(method, f"{BACKEND_URL}{path}", **kwargs)
    except NOT_SENT as exc:  # refused, DNS, connect timeout, URL without http://
        raise BackendUnavailable(
            f"Cannot reach the backend at {BACKEND_URL}. "
            "Start it (docker compose up) and reload the page."
        ) from exc
    except httpx.TransportError as exc:  # sent, but no complete reply
        if method == "GET":
            raise BackendNoAnswer(
                "The backend took too long to answer. Reload the page to try again."
            ) from exc
        raise BackendNoAnswer(
            "The backend did not answer in time. Your change may have been saved. "
            "Reload the page and check before trying again."
        ) from exc
    if response.is_error:
        raise BackendError(_friendly(response))
    return response


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:  # not JSON, e.g. an HTML page from another server
        raise BackendError(
            f"The service at {BACKEND_URL} did not answer like the eliezer API. "
            "Check BACKEND_URL."
        ) from exc


def list_items() -> list[Item]:
    return _json(_request("GET", "/items", params={"limit": 100}))


def create_item(item: dict) -> Item:
    return _json(_request("POST", "/items", json=item))


def update_item(item_id: int, changes: dict) -> Item:
    return _json(_request("PATCH", f"/items/{item_id}", json=changes))


def delete_item(item_id: int) -> None:
    _request("DELETE", f"/items/{item_id}")


def create_from_text(text: str) -> Item:
    return _json(
        _request("POST", "/items/from-text", json={"text": text}, timeout=AI_TIMEOUT)
    )
