"""POST /care: the care agent, its tools and its validator."""

import json

import pytest
from pydantic_ai import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from app.agents import DEMO_CARE, care_agent, season_for_month

PLANT = {"scientific_name": "Ficus carica", "name_en": "Fig", "name_he": "תאנה"}
GOOD = {
    "watering_interval_days": 10,
    "sunlight": "full_sun",
    "care_en": ["Water deeply in summer.", "Plant in full sun.", "Prune in winter."],
    "care_he": ["השקו לעומק בקיץ.", "שתלו בשמש מלאה.", "גזמו בחורף."],
}


def scripted(outputs: list[dict]) -> FunctionModel:
    """Look up the garden context and the season, then return each output in turn."""
    replies = iter(outputs)

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        returns = {
            p.tool_name: p.content
            for m in messages
            for p in getattr(m, "parts", [])
            if isinstance(p, ToolReturnPart)
        }
        if "garden_context" not in returns:
            return ModelResponse(parts=[ToolCallPart("garden_context", {})])
        if "season_for_month" not in returns:
            month = returns["garden_context"]["month"]
            return ModelResponse(
                parts=[ToolCallPart("season_for_month", {"month": month})]
            )
        output_tool = info.output_tools[0].name
        return ModelResponse(
            parts=[ToolCallPart(output_tool, json.dumps(next(replies)))]
        )

    return FunctionModel(respond)


def test_demo_mode_answers_without_a_model(client):
    r = client.post("/care", json=PLANT)
    assert r.status_code == 200
    assert r.json() == DEMO_CARE.model_dump()


def test_tools_use_the_injected_garden_context(client):
    seen = []

    def respond(messages, info):
        seen.append(messages)
        return scripted([GOOD]).function(messages, info)

    with care_agent.override(model=FunctionModel(respond)):
        r = client.post("/care", json=PLANT)
    assert r.status_code == 200
    assert r.json() == GOOD
    returns = {
        p.tool_name: p.content
        for m in seen[-1]
        for p in getattr(m, "parts", [])
        if isinstance(p, ToolReturnPart)
    }
    assert returns["garden_context"] == {
        "region": "Israel (Mediterranean climate)",
        "month": 7,
    }
    assert returns["season_for_month"] == "summer (hot and dry)"
    prompt = seen[0][0].parts[-1].content
    assert "Ficus carica" in prompt and "תאנה" in prompt


def test_testmodel_can_call_every_tool(client):
    # TestModel invents tool arguments; season_for_month's limits keep them valid.
    with care_agent.override(model=TestModel(custom_output_args=GOOD)):
        r = client.post("/care", json=PLANT)
    assert r.status_code == 200


def test_season_for_month_is_a_plain_function():
    assert season_for_month(1) == "winter (rainy season)"
    assert season_for_month(7) == "summer (hot and dry)"


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(
            {**GOOD, "care_he": ["Water deeply.", "Full sun.", "Prune."]},
            id="english-in-hebrew",
        ),
        pytest.param(
            {**GOOD, "care_en": ["השקו.", "Plant in sun.", "Prune."]},
            id="hebrew-in-english",
        ),
        pytest.param(
            {**GOOD, "care_en": ["**Water** deeply.", "- Full sun.", "Prune."]},
            id="markdown",
        ),
    ],
)
def test_validator_sends_bad_guides_back(client, bad):
    with care_agent.override(model=scripted([bad, GOOD])):
        r = client.post("/care", json=PLANT)
    assert r.status_code == 200
    assert r.json() == GOOD


def test_out_of_range_interval_is_502_after_retries(client):
    with care_agent.override(
        model=scripted([{**GOOD, "watering_interval_days": 90}] * 5)
    ):
        r = client.post("/care", json=PLANT)
    assert r.status_code == 502


def test_request_validation_is_422(client):
    for body in (
        {**PLANT, "scientific_name": ""},
        {**PLANT, "name_he": "x" * 121},
        {**PLANT, "extra": True},
        {"name_en": "Fig"},
    ):
        assert client.post("/care", json=body).status_code == 422, body


def test_usage_limit_is_429(client):
    def loops_forever(messages, info):  # never answers, keeps calling a tool
        return ModelResponse(parts=[ToolCallPart("season_for_month", {"month": 3})])

    with care_agent.override(model=FunctionModel(loops_forever)):
        r = client.post("/care", json=PLANT)
    assert r.status_code == 429  # not 503: the backend must not retry a spent budget
    assert r.json() == {"detail": "AI budget exceeded"}


def test_plain_text_answer_is_retried_then_502(client):
    def chatty(messages, info):
        return ModelResponse(parts=[TextPart("Figs love the sun!")])

    with care_agent.override(model=FunctionModel(chatty)):
        assert client.post("/care", json=PLANT).status_code == 502
