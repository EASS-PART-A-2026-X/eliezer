"""POST /plants/identify with the ai-service faked by httpx.MockTransport.

No network: these tests pass with Wi-Fi off.
"""

import base64
import json
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.ai_client import CARE_TIMEOUT, IDENTIFY_TIMEOUT
from tests.helpers import image_bytes

ROSEMARY = {
    "scientific_name": "Salvia rosmarinus",
    "name_en": "Rosemary",
    "name_he": "רוזמרין",
    "confidence": 0.8,
}
REPLY = {
    "is_plant": True,
    "model": "ollama:gemma4:e2b",
    "candidates": [
        ROSEMARY,
        {
            "scientific_name": "Rosa chinensis",
            "name_en": "China rose",
            "name_he": "ורד סיני",
            "confidence": 0.1,
        },
        {
            "scientific_name": "Citrus limon",
            "name_en": "Lemon",
            "name_he": "לימון",
            "confidence": 0.05,
        },
    ],
}
DETAIL = {502: "AI service returned invalid output", 503: "AI service unavailable"}


def identify(client, data=None, name="plant.jpg", mime="image/jpeg"):
    data = image_bytes("JPEG", (1600, 1200)) if data is None else data
    return client.post("/plants/identify", files={"photo": (name, data, mime)})


def test_candidates_are_matched_to_the_catalog(client, catalog, fake_ai):
    calls = fake_ai(lambda request: httpx.Response(200, json=REPLY))
    r = identify(client)
    assert r.status_code == 200
    body = r.json()
    assert (body["is_plant"], body["model"]) == (True, "ollama:gemma4:e2b")
    found = [(c["plant_id"], c["matched_on"]) for c in body["candidates"]]
    assert found == [
        (catalog["Salvia rosmarinus"].id, "species"),
        (catalog["Rosa"].id, "genus"),  # no "Rosa chinensis" row; the genus exists
        (catalog["Citrus × limon"].id, "species"),  # "×" spacing is normalized
    ]
    [sent] = calls
    assert sent.url.path == "/identify"
    sent_body = json.loads(sent.content)
    assert sent_body["media_type"] == "image/jpeg"
    sent_image = Image.open(BytesIO(base64.b64decode(sent_body["image_b64"])))
    assert max(sent_image.size) == 1024  # downscaled before it leaves the backend


def test_unknown_plants_have_no_plant_id(client, catalog, fake_ai):
    unknown = {**ROSEMARY, "scientific_name": "Welwitschia mirabilis"}
    fake_ai(
        lambda request: httpx.Response(200, json={**REPLY, "candidates": [unknown]})
    )
    [candidate] = identify(client).json()["candidates"]
    assert (candidate["plant_id"], candidate["matched_on"]) == (None, None)


def test_not_a_plant_has_no_candidates(client, catalog, fake_ai):
    fake_ai(lambda request: httpx.Response(200, json={**REPLY, "is_plant": False}))
    body = identify(client).json()
    assert (body["is_plant"], body["candidates"]) == (False, [])


def test_identify_writes_nothing(client, catalog, fake_ai):
    fake_ai(lambda request: httpx.Response(200, json=REPLY))
    identify(client)
    assert client.get("/garden").json() == []


@pytest.mark.parametrize(
    "data", [pytest.param(b"", id="empty"), pytest.param(b"%PDF-1.7", id="not-image")]
)
def test_invalid_photo_makes_no_ai_call(client, fake_ai, data):
    calls = fake_ai(lambda request: httpx.Response(200, json=REPLY))
    r = identify(client, data)
    assert r.status_code == 422
    assert calls == []  # rejected at the edge: no model call, no cost


def test_missing_photo_field_is_422(client):
    assert client.post("/plants/identify").status_code == 422


def test_broken_contract_is_502(client, fake_ai):
    fake_ai(lambda request: httpx.Response(200, json={"species": "rosemary"}))
    r = identify(client)
    assert r.status_code == 502
    assert r.json() == {"detail": DETAIL[502]}


def test_more_than_three_candidates_breaks_the_contract(client, fake_ai):
    many = {**REPLY, "candidates": [ROSEMARY] * 4}
    fake_ai(lambda request: httpx.Response(200, json=many))
    assert identify(client).status_code == 502


# --- retry policy: only "never reached it" and 503 are retried --------------------
def test_ai_down_is_503_after_three_attempts(client, fake_ai):
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    calls = fake_ai(refuse)
    r = identify(client)
    assert r.status_code == 503
    assert r.json() == {"detail": DETAIL[503]}
    assert len(calls) == 3


def test_503_is_retried_then_succeeds(client, catalog, fake_ai):
    replies = iter([httpx.Response(503), httpx.Response(503)])
    calls = fake_ai(lambda request: next(replies, httpx.Response(200, json=REPLY)))
    assert identify(client).status_code == 200
    assert len(calls) == 3


def test_read_timeout_is_not_retried(client, fake_ai):
    def slow(request):
        raise httpx.ReadTimeout("model took too long", request=request)

    calls = fake_ai(slow)
    assert identify(client).status_code == 503
    assert len(calls) == 1  # a CPU model that timed out would time out again


@pytest.mark.parametrize(
    ("ai_status", "expected"),
    [
        pytest.param(504, 503, id="model-timeout-504"),  # slow generation: no retry
        pytest.param(429, 503, id="budget-429"),  # a retry would hit the same cap
        pytest.param(500, 503, id="crash-500"),  # fail fast
        pytest.param(502, 502, id="invalid-output-502"),  # agent already retried
        pytest.param(422, 502, id="our-bug-422"),  # we broke the contract
    ],
)
def test_not_retried(client, fake_ai, ai_status, expected):
    calls = fake_ai(lambda request: httpx.Response(ai_status))
    r = identify(client)
    assert r.status_code == expected
    assert r.json() == {"detail": DETAIL[expected]}
    assert len(calls) == 1


def test_timeouts_are_explicit_and_above_the_ai_caps():
    assert (IDENTIFY_TIMEOUT.connect, IDENTIFY_TIMEOUT.read) == (2.0, 170.0)
    assert (CARE_TIMEOUT.connect, CARE_TIMEOUT.read) == (2.0, 220.0)
