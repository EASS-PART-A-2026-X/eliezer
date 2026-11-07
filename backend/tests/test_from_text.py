"""POST /items/from-text with the ai-service faked by httpx.MockTransport.

No network: these tests pass with Wi-Fi off.
"""

import json

import httpx
import pytest

from app.ai_client import TIMEOUT, AIClient, get_ai_client
from app.main import app

# What a good POST /extract reply looks like (the ai-service contract).
GOOD = {
    "title": "Send the report",
    "description": "Quarterly numbers for the client.",
    "priority": 5,
    "tags": ["work", "follow-up"],
}
DETAIL = {502: "AI service returned invalid output", 503: "AI service unavailable"}


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    # tenacity waits between attempts; make it instant in tests.
    monkeypatch.setattr(AIClient._post_extract.retry, "sleep", lambda seconds: None)


@pytest.fixture
def fake_ai(client):
    """fake_ai(handler) routes the backend's ai-service calls to handler(request)."""
    calls: list[httpx.Request] = []

    def install(handler):
        def recording(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return handler(request)

        ai = AIClient("http://ai-service", transport=httpx.MockTransport(recording))
        app.dependency_overrides[get_ai_client] = lambda: ai
        return calls

    return install


def post_text(client, text="URGENT: send the quarterly report to the client"):
    return client.post("/items/from-text", json={"text": text})


def test_success_stores_the_item(client, fake_ai):
    calls = fake_ai(lambda request: httpx.Response(200, json=GOOD))
    r = post_text(client)
    assert r.status_code == 201
    saved = r.json()
    assert saved["tags"] == "work,follow-up"  # the adapter ran
    assert saved["priority"] == 5
    assert client.get(f"/items/{saved['id']}").json() == saved  # really stored
    [sent] = calls  # exactly one call to the ai-service
    assert (sent.method, sent.url.path) == ("POST", "/extract")
    assert json.loads(sent.content) == {
        "text": "URGENT: send the quarterly report to the client"
    }


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("", id="empty"),
        pytest.param("  \n\t ", id="whitespace-only"),
        pytest.param("x" * 5001, id="too-long"),
    ],
)
def test_invalid_text_makes_no_ai_call(client, fake_ai, text):
    calls = fake_ai(lambda request: httpx.Response(200, json=GOOD))
    assert post_text(client, text).status_code == 422
    assert calls == []  # rejected at the edge: no model call, no cost


def test_broken_contract_is_502(client, fake_ai):
    fake_ai(lambda request: httpx.Response(200, json={"name": "no title here"}))
    r = post_text(client)
    assert r.status_code == 502
    assert r.json() == {"detail": DETAIL[502]}
    assert client.get("/items").json() == []  # nothing saved


def test_non_json_body_is_502(client, fake_ai):
    fake_ai(lambda request: httpx.Response(200, text="<html>oops</html>"))
    assert post_text(client).status_code == 502


@pytest.mark.parametrize(
    ("ai_status", "expected"),
    [
        pytest.param(429, 503, id="budget-429"),  # a retry would hit the same cap
        pytest.param(502, 502, id="invalid-output-502"),  # agent already retried
        pytest.param(500, 503, id="crash-500"),  # fail fast
        pytest.param(422, 502, id="our-bug-422"),  # we broke the contract
    ],
)
def test_not_retried(client, fake_ai, ai_status, expected):
    calls = fake_ai(lambda request: httpx.Response(ai_status))
    r = post_text(client)
    assert r.status_code == expected
    assert r.json() == {"detail": DETAIL[expected]}
    assert len(calls) == 1  # one try: retries live in one layer only


def test_ai_down_is_503_after_three_attempts(client, fake_ai):
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    calls = fake_ai(refuse)
    r = post_text(client)
    assert r.status_code == 503
    assert r.json() == {"detail": DETAIL[503]}
    assert len(calls) == 3  # bounded retries
    assert client.get("/items").json() == []  # nothing half-saved


def test_ai_timeout_is_503_after_three_attempts(client, fake_ai):
    def slow(request):
        raise httpx.ReadTimeout("model took too long", request=request)

    calls = fake_ai(slow)
    r = post_text(client)
    assert r.status_code == 503
    assert len(calls) == 3


def test_503_and_504_are_retried_then_succeed(client, fake_ai):
    replies = iter([httpx.Response(503), httpx.Response(504)])
    calls = fake_ai(lambda request: next(replies, httpx.Response(200, json=GOOD)))
    assert post_text(client).status_code == 201
    assert len(calls) == 3


def test_timeouts_are_explicit():
    phases = (TIMEOUT.connect, TIMEOUT.read, TIMEOUT.write, TIMEOUT.pool)
    assert phases == (2.0, 30.0, 5.0, 2.0)
    ai = AIClient()
    assert ai._http.timeout == TIMEOUT
    ai.close()
