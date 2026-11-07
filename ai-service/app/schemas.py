"""The ai-service contract. The backend keeps a copy (backend/app/ai_client.py);
backend/tests/test_contract.py fails if the two drift apart.

PLACEHOLDER DOMAIN: change ItemExtraction together with the backend's Item.
"""

from pydantic import BaseModel, ConfigDict, Field


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=5000)


class ItemExtraction(BaseModel):
    """One item extracted from the user's text."""

    # The docstring above is model-facing: Pydantic AI sends it as the output
    # tool's description. Keep notes for developers in comments like this one.
    title: str = Field(min_length=1, max_length=200, description="Short title")
    description: str = Field(
        default="", max_length=5000, description="Remaining details, or empty"
    )
    priority: int = Field(
        default=3, ge=1, le=5, description="1 lowest to 5 most urgent; default 3"
    )
    tags: list[str] = Field(default_factory=list, description="Allowed tags only")
