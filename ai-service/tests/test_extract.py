"""The agent and POST /extract, with deterministic fake models only."""

import asyncio
import json

from pydantic_ai import (
    ModelHTTPError,
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from app import main
from app.agent import Deps, extract_agent, priority_for

GOOD = {
    "title": "Send the report",
    "description": "Quarterly numbers for the client.",
    "priority": 5,
    "tags": ["work"],
}


def scripted_model(outputs: list[dict]) -> FunctionModel:
    """A fake model: first calls allowed_tags, then returns each output in turn."""
    replies = iter(outputs)

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len(messages) == 1:  # first request: look up the allowed tags
            return ModelResponse(parts=[ToolCallPart("allowed_tags", {})])
        output_tool = info.output_tools[0].name  # the structured-output "tool"
        return ModelResponse(
            parts=[ToolCallPart(output_tool, json.dumps(next(replies)))]
        )

    return FunctionModel(respond)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_extract_happy_path(client):
    # TestModel calls every tool once, then returns exactly these output args.
    with extract_agent.override(model=TestModel(custom_output_args=GOOD)):
        r = client.post("/extract", json={"text": "URGENT: send the report"})
    assert r.status_code == 200
    assert r.json() == GOOD


def test_request_validation_is_422(client):
    bodies = ({"text": ""}, {"text": "   "}, {"text": "x" * 5001}, {"txt": "hi"})
    for body in bodies:
        assert client.post("/extract", json=body).status_code == 422, body


def test_default_testmodel_output_is_schema_valid():
    # Without custom args TestModel invents schema-valid data (what compose runs).
    with extract_agent.override(model=TestModel()):
        result = extract_agent.run_sync("anything", deps=Deps())
    assert 1 <= result.output.priority <= 5
    assert result.output.title
    assert result.usage.requests == 2


def test_tools_are_plain_functions():
    assert priority_for("URGENT ") == 5
    assert priority_for("low") == 1
    assert priority_for("whenever") == 3  # unknown word: the default


def test_unknown_tag_makes_the_model_retry(client):
    bad = {**GOOD, "tags": ["admin"]}  # not allowed -> ModelRetry -> try again
    with extract_agent.override(model=scripted_model([bad, GOOD])):
        r = client.post("/extract", json={"text": "send the report"})
    assert r.status_code == 200
    assert r.json()["tags"] == ["work"]


def test_malformed_output_is_502_after_retries(client):
    junk = {"title": "", "priority": 99}
    with extract_agent.override(model=scripted_model([junk] * 5)):
        r = client.post("/extract", json={"text": "send the report"})
    assert r.status_code == 502
    assert r.json() == {"detail": "AI returned invalid output"}


def test_plain_text_instead_of_structured_output_is_502(client):
    def chatty(messages, info):
        return ModelResponse(parts=[TextPart("Sure! Here is a lovely item...")])

    with extract_agent.override(model=FunctionModel(chatty)):
        assert client.post("/extract", json={"text": "x"}).status_code == 502


def test_usage_limit_is_429(client):
    def loops_forever(messages, info):  # never answers, keeps calling a tool
        return ModelResponse(parts=[ToolCallPart("priority_for", {"urgency": "low"})])

    with extract_agent.override(model=FunctionModel(loops_forever)):
        r = client.post("/extract", json={"text": "x"})
    assert r.status_code == 429  # not 503: the backend must not retry a spent budget
    assert r.json() == {"detail": "AI budget exceeded"}


def test_slow_model_is_504(client, monkeypatch):
    async def slow(messages, info):
        await asyncio.sleep(1)
        return ModelResponse(parts=[TextPart("too late")])

    monkeypatch.setattr(main, "MODEL_TIMEOUT_SECONDS", 0.05)
    with extract_agent.override(model=FunctionModel(slow)):
        assert client.post("/extract", json={"text": "x"}).status_code == 504


def test_provider_failure_is_500_not_retried(client):
    def rate_limited(messages, info):  # what a provider's 429 looks like here
        raise ModelHTTPError(status_code=429, model_name="test")

    with extract_agent.override(model=FunctionModel(rate_limited)):
        r = client.post("/extract", json={"text": "x"})
    assert r.status_code == 500  # the backend fails fast on 500: no second layer
    assert r.json() == {"detail": "AI provider failed"}


def test_logs_do_not_contain_user_text(client, caplog):
    secret = "my private note 12345"
    caplog.set_level("INFO", logger="ai-service")
    with extract_agent.override(model=TestModel(custom_output_args=GOOD)):
        assert client.post("/extract", json={"text": secret}).status_code == 200
    assert "extract ok" in caplog.text
    assert secret not in caplog.text
