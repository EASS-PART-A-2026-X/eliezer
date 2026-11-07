"""POST /identify with deterministic fake models only."""

import asyncio
import base64
import json

import pytest
from pydantic_ai import (
    BinaryContent,
    ModelAPIError,
    ModelHTTPError,
    ModelMessage,
    ModelResponse,
    TextPart,
    UserError,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app import main
from app.agents import DEMO_IDENTIFICATION, identify_agent, model_settings
from tests.conftest import JPEG_B64, png_bytes

ROSEMARY = {
    "scientific_name": "Salvia rosmarinus",
    "name_en": "Rosemary",
    "name_he": "רוזמרין",
    "confidence": 0.7,
}
LAVENDER = {
    "scientific_name": "Lavandula angustifolia",
    "name_en": "Lavender",
    "name_he": "לבנדר",
    "confidence": 0.2,
}
GOOD = {"is_plant": True, "candidates": [ROSEMARY, LAVENDER]}


def scripted(outputs: list[dict]) -> FunctionModel:
    """A fake model that answers each request with the next JSON output."""
    replies = iter(outputs)

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(next(replies)))])

    return FunctionModel(respond)


def post(client, image_b64=JPEG_B64, media_type="image/jpeg"):
    return client.post(
        "/identify", json={"image_b64": image_b64, "media_type": media_type}
    )


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_demo_mode_answers_without_a_model(client):
    r = post(client)  # AI_MODEL is unset in tests: demo mode
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "demo"
    assert body["candidates"] == DEMO_IDENTIFICATION.model_dump()["candidates"]


def test_happy_path_sends_the_photo_and_region(client):
    seen: list[list[ModelMessage]] = []

    def respond(messages, info):
        seen.append(messages)
        return ModelResponse(parts=[TextPart(json.dumps(GOOD))])

    with identify_agent.override(model=FunctionModel(respond)):
        r = post(client)
    assert r.status_code == 200
    assert r.json()["candidates"] == [ROSEMARY, LAVENDER]
    [request] = seen[0]
    images = [
        p
        for part in request.parts
        for p in getattr(part, "content", [])
        if isinstance(p, BinaryContent)
    ]
    assert images and images[0].media_type == "image/jpeg"
    assert base64.b64encode(images[0].data).decode() == JPEG_B64
    assert "Israel" in request.instructions


def test_request_validation_is_422(client):
    for body in (
        {"image_b64": "", "media_type": "image/jpeg"},
        {"image_b64": "!!not base64!!", "media_type": "image/jpeg"},
        {"image_b64": JPEG_B64, "media_type": "image/gif"},
        {"image_b64": JPEG_B64, "media_type": "image/jpeg", "extra": 1},
        {"media_type": "image/jpeg"},
    ):
        assert client.post("/identify", json=body).status_code == 422, body


def test_wrong_file_signature_is_422(client):
    png_as_jpeg = base64.b64encode(png_bytes()).decode()
    r = post(client, png_as_jpeg, "image/jpeg")
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "image_b64"]
    assert post(client, png_as_jpeg, "image/png").status_code == 200  # demo answer


def test_not_a_plant_returns_no_candidates(client):
    with identify_agent.override(
        model=scripted([{"is_plant": False, "candidates": []}])
    ):
        r = post(client)
    assert r.status_code == 200
    assert (r.json()["is_plant"], r.json()["candidates"]) == (False, [])


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(
            {"is_plant": False, "candidates": [ROSEMARY]},
            id="not-plant-with-candidates",
        ),
        pytest.param(
            {"is_plant": True, "candidates": []}, id="plant-without-candidates"
        ),
        pytest.param(
            {"is_plant": True, "candidates": [{**ROSEMARY, "name_he": "Rosemary"}]},
            id="hebrew-name-in-english",
        ),
        pytest.param(
            {
                "is_plant": True,
                "candidates": [{**ROSEMARY, "scientific_name": "rosemary bush!"}],
            },
            id="not-a-scientific-name",
        ),
    ],
)
def test_validator_sends_bad_answers_back(client, bad):
    with identify_agent.override(model=scripted([bad, GOOD])):
        r = post(client)
    assert r.status_code == 200  # the second, valid answer
    assert r.json()["candidates"][0]["scientific_name"] == "Salvia rosmarinus"


def test_fixable_answers_are_repaired_without_asking_again(client):
    # One answer only: a second model call would exhaust the script and fail.
    sweet_basil = {**LAVENDER, "scientific_name": "Sweet Basil"}  # seen with Gemma
    answer = {"is_plant": True, "candidates": [LAVENDER, sweet_basil, ROSEMARY]}
    with identify_agent.override(model=scripted([answer])):
        r = post(client)
    assert r.status_code == 200
    names = [c["scientific_name"] for c in r.json()["candidates"]]
    assert names == ["Salvia rosmarinus", "Lavandula angustifolia"]  # sorted, cleaned


def test_persistent_junk_is_502_after_retries(client):
    junk = {"is_plant": True, "candidates": [{**ROSEMARY, "name_he": "no hebrew"}]}
    with identify_agent.override(model=scripted([junk] * 5)):
        r = post(client)
    assert r.status_code == 502
    assert r.json() == {"detail": "AI returned invalid output"}


def test_more_than_three_candidates_is_502(client):
    four = {"is_plant": True, "candidates": [ROSEMARY] * 4}
    with identify_agent.override(model=scripted([four] * 5)):
        assert post(client).status_code == 502


def test_slow_model_is_504(client, monkeypatch):
    async def slow(messages, info):
        await asyncio.sleep(1)
        return ModelResponse(parts=[TextPart("too late")])

    monkeypatch.setattr(main, "IDENTIFY_TIMEOUT_SECONDS", 0.05)
    with identify_agent.override(model=FunctionModel(slow)):
        r = post(client)
    assert r.status_code == 504
    assert r.json() == {"detail": "AI model timed out"}


@pytest.mark.parametrize(
    ("error", "detail"),
    [
        pytest.param(
            ModelHTTPError(status_code=429, model_name="m"),
            "AI provider failed",
            id="provider-429",
        ),
        pytest.param(
            ModelHTTPError(status_code=404, model_name="m"),
            "AI model misconfigured",
            id="model-not-pulled",
        ),
        pytest.param(
            ModelAPIError(model_name="m", message="Connection error."),
            "AI provider failed",
            id="ollama-down",
        ),
        pytest.param(
            UserError("Set the `OLLAMA_BASE_URL` environment variable"),
            "AI model misconfigured",
            id="no-base-url",
        ),
    ],
)
def test_provider_problems_are_500(client, error, detail):
    def fail(messages, info):
        raise error

    with identify_agent.override(model=FunctionModel(fail)):
        r = post(client)
    assert r.status_code == 500  # the backend fails fast on 500: no second layer
    assert r.json() == {"detail": detail}


def test_logs_do_not_contain_the_photo(client, caplog):
    caplog.set_level("INFO", logger="ai-service")
    assert post(client).status_code == 200
    assert "identify ok" in caplog.text
    assert JPEG_B64[:40] not in caplog.text


def test_ollama_models_answer_without_thinking():
    # Gemma 4 on Ollama otherwise writes ~800 hidden tokens before every answer.
    assert model_settings(0.2, "ollama:gemma4:e2b") == {
        "temperature": 0.2,
        "openai_reasoning_effort": "none",
    }
    # Other providers' non-reasoning models reject the setting.
    assert model_settings(0.2, "openai:gpt-4.1") == {"temperature": 0.2}
