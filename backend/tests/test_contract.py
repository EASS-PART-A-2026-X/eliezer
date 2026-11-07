"""The backend's copy of the contract must match what the ai-service publishes.

Regenerate the snapshot after every ai-service schema change (README, "Test"):
    cd ai-service && uv run python -c "import json; from app.main import app; \
print(json.dumps(app.openapi()))" > ../backend/tests/ai_openapi.json
"""

import json
from pathlib import Path

from app.ai_client import (
    Candidate,
    CareGuideOut,
    CareRequest,
    IdentifyRequest,
    PlantIdentification,
)

PUBLISHED = json.loads((Path(__file__).parent / "ai_openapi.json").read_text())
SCHEMAS = PUBLISHED["components"]["schemas"]
IGNORED = {"title", "description"}


def strip(rules):
    """Types and limits only; "$ref" paths reduced to the schema's name."""
    if isinstance(rules, dict):
        return {
            k: (v.rsplit("/", 1)[-1] if k == "$ref" else strip(v))
            for k, v in rules.items()
            if k not in IGNORED
        }
    if isinstance(rules, list):
        return [strip(r) for r in rules]
    return rules


def fields(schema: dict) -> dict:
    return {name: strip(rules) for name, rules in schema["properties"].items()}


def test_responses_have_every_field_we_read():
    # Each field we read must exist on their side with the same type and limits.
    # Extra fields on their side are fine: our models ignore unknown fields.
    for ours, theirs in (
        (PlantIdentification, "PlantIdentification"),
        (Candidate, "Candidate"),
        (CareGuideOut, "CareGuide"),
    ):
        our_fields = fields(ours.model_json_schema())
        their_fields = fields(SCHEMAS[theirs])
        assert {name: their_fields.get(name) for name in our_fields} == our_fields, (
            theirs
        )


def test_requests_match_exactly():
    # What we send must be exactly what they accept (they forbid extra fields).
    assert fields(IdentifyRequest.model_json_schema()) == fields(
        SCHEMAS["IdentifyRequest"]
    )
    assert fields(CareRequest.model_json_schema()) == fields(SCHEMAS["CareRequest"])


def test_paths_exist():
    assert {"/identify", "/care", "/health"} <= set(PUBLISHED["paths"])
