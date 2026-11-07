"""The backend's copy of the contract must match what the ai-service publishes.

Regenerate the snapshot after every ai-service schema change (see README, "Test"):
    cd ai-service && uv run python -c "import json; from app.main import app; \
print(json.dumps(app.openapi()))" > ../backend/tests/ai_openapi.json
"""

import json
from pathlib import Path

from app.ai_client import ItemExtraction
from app.models import FromTextRequest

PUBLISHED = json.loads((Path(__file__).parent / "ai_openapi.json").read_text())
SCHEMAS = PUBLISHED["components"]["schemas"]


def fields(schema: dict) -> dict:
    """Field names, types and limits. Titles and descriptions do not matter."""
    return {
        name: {k: v for k, v in rules.items() if k not in ("title", "description")}
        for name, rules in schema["properties"].items()
    }


def test_backend_and_ai_service_agree():
    # Response: each field we read must exist on their side, same type and limits.
    # Extra fields on their side are fine: our model ignores unknown fields.
    ours = fields(ItemExtraction.model_json_schema())
    theirs = fields(SCHEMAS["ItemExtraction"])
    assert {name: theirs.get(name) for name in ours} == ours
    # Request: the text we accept must be exactly the text they accept.
    our_text = fields(FromTextRequest.model_json_schema())["text"]
    assert fields(SCHEMAS["ExtractRequest"])["text"] == our_text
