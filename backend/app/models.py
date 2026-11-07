"""The main record and its API models.

PLACEHOLDER DOMAIN: rename `Item` and its fields to your product's main record
(REQUIREMENTS.md, section 0). Keep the pattern: one table model, separate
Create / Update / Public models, extra="forbid", and a limit on every field.
"""

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=200, index=True)
    description: str = Field(default="", max_length=5000)
    priority: int = Field(default=3, ge=1, le=5)  # 1 lowest, 5 most urgent
    tags: str = Field(default="", max_length=500)  # comma-separated


class Item(ItemBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class ItemCreate(ItemBase):
    """POST body: clients cannot set `id`."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ItemUpdate(SQLModel):
    """PATCH body: every field optional; only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    priority: int | None = Field(default=None, ge=1, le=5)
    tags: str | None = Field(default=None, max_length=500)


class ItemPublic(ItemBase):
    """Response body: always includes `id`."""

    id: int


class FromTextRequest(SQLModel):
    """POST /items/from-text body: free text for the AI service to read."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=5000)
