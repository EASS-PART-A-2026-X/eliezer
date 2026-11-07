"""Every HTTP call to the backend lives here. The UI never sees httpx.

Errors carry a `kind` (and values for the message); the UI turns that into a
sentence in the user's language with i18n.t(f"err_{kind}", ...).
"""

import os
from typing import Any

import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TIMEOUT = httpx.Timeout(10.0, connect=2.0)
# Above the backend's worst case (one AI attempt of up to 170 s / 220 s).
IDENTIFY_TIMEOUT = httpx.Timeout(200.0, connect=2.0)
CARE_TIMEOUT = httpx.Timeout(250.0, connect=2.0)
NOT_SENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.UnsupportedProtocol)


class BackendError(Exception):
    """Something went wrong; `kind` and `values` describe it for the UI."""

    def __init__(self, kind: str, **values) -> None:
        super().__init__(kind)
        self.kind = kind
        self.values = values


def _error_for(response: httpx.Response) -> BackendError:
    match response.status_code:
        case 422:
            detail = response.json()["detail"]
            problems = "; ".join(f"{err['loc'][-1]}: {err['msg']}" for err in detail)
            return BackendError("validation", problems=problems)
        case 404:
            return BackendError("not_found")
        case 409:
            return BackendError("conflict")
        case 503:
            return BackendError("ai_unavailable")
        case 502:
            return BackendError("ai_bad_output")
        case code:
            return BackendError("server", code=code)


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", TIMEOUT)
    try:
        response = httpx.request(method, f"{BACKEND_URL}{path}", **kwargs)
    except NOT_SENT as exc:  # refused, DNS, connect timeout, URL without http://
        raise BackendError("unavailable", url=BACKEND_URL) from exc
    except httpx.TransportError as exc:  # sent, but no complete reply
        kind = "no_answer_read" if method == "GET" else "no_answer_write"
        raise BackendError(kind) from exc
    if response.is_error:
        raise _error_for(response)
    return response


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:  # not JSON, e.g. an HTML page from another server
        raise BackendError("not_api", url=BACKEND_URL) from exc


# --- garden ----------------------------------------------------------------------------
def list_garden() -> list[dict]:
    return _json(_request("GET", "/garden"))


def add_to_garden(plant_id: int, nickname: str = "") -> dict:
    body = {"plant_id": plant_id, "nickname": nickname.strip() or None}
    return _json(_request("POST", "/garden", json=body))


def update_garden(garden_id: int, changes: dict) -> dict:
    return _json(_request("PATCH", f"/garden/{garden_id}", json=changes))


def remove_from_garden(garden_id: int) -> None:
    _request("DELETE", f"/garden/{garden_id}")


def water(garden_id: int) -> dict:
    return _json(_request("POST", f"/garden/{garden_id}/water"))


def get_photo(garden_id: int) -> bytes | None:
    try:
        return _request("GET", f"/garden/{garden_id}/photo").content
    except BackendError as exc:
        if exc.kind == "not_found":
            return None
        raise


def upload_photo(garden_id: int, data: bytes, filename: str, mime: str) -> None:
    files = {"photo": (filename, data, mime)}
    _request("PUT", f"/garden/{garden_id}/photo", files=files)


# --- catalog ----------------------------------------------------------------------------
def search_plants(q: str) -> list[dict]:
    return _json(_request("GET", "/plants", params={"q": q, "limit": 20}))


def create_plant(scientific_name: str, name_en: str, name_he: str) -> dict:
    body = {"scientific_name": scientific_name, "name_en": name_en, "name_he": name_he}
    return _json(_request("POST", "/plants", json=body))


def write_care(plant_id: int) -> dict:
    return _json(_request("POST", f"/plants/{plant_id}/care", timeout=CARE_TIMEOUT))


def identify(data: bytes, filename: str, mime: str) -> dict:
    files = {"photo": (filename, data, mime)}
    return _json(
        _request("POST", "/plants/identify", files=files, timeout=IDENTIFY_TIMEOUT)
    )
