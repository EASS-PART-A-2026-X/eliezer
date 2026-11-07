"""Eliezer's records and API models.

Plant          the catalog (Wikidata names + curated or AI-written care)
GardenPlant    a plant in *your* garden, with its watering schedule
GardenPhoto    an optional thumbnail, in its own table so listing never loads blobs
"""

import re
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import ConfigDict, StringConstraints, field_validator
from sqlalchemy import JSON, Column
from sqlmodel import AutoString, Field, SQLModel

HEBREW = re.compile(r"[֐-׿]")


def has_hebrew(text: str) -> bool:
    return bool(HEBREW.search(text))


class Sunlight(StrEnum):
    FULL_SUN = "full_sun"
    PARTIAL_SHADE = "partial_shade"
    SHADE = "shade"


class CareSource(StrEnum):
    CURATED = "curated"  # hand-written general guidance (app/data/care_curated.json)
    AI = "ai"  # written by the AI service, validated, then stored
    NONE = "none"  # not written yet


Step = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]


# --- catalog ---------------------------------------------------------------------
class PlantBase(SQLModel):
    scientific_name: str = Field(min_length=1, max_length=120, unique=True, index=True)
    name_en: str = Field(min_length=1, max_length=120)
    name_he: str = Field(min_length=1, max_length=120)
    wikidata_id: str | None = Field(default=None, max_length=20)


class Plant(PlantBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    watering_interval_days: int | None = Field(default=None, ge=1, le=60)
    sunlight: Sunlight | None = Field(default=None, sa_type=AutoString)
    # none_as_null: a missing guide is SQL NULL, not the JSON value null.
    # Always assign a new list; in-place edits of a JSON column are not detected.
    care_en: list[str] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True))
    )
    care_he: list[str] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True))
    )
    care_source: CareSource = Field(default=CareSource.NONE, sa_type=AutoString)


class PlantPublic(PlantBase):
    id: int
    watering_interval_days: int | None
    sunlight: Sunlight | None
    care_en: list[str] | None
    care_he: list[str] | None
    care_source: CareSource


class PlantCreate(SQLModel):
    """POST /plants: a plant the AI identified that the catalog does not have."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scientific_name: Name
    name_en: Name
    name_he: Name

    @field_validator("name_he")
    @classmethod
    def hebrew_name(cls, value: str) -> str:
        if not has_hebrew(value):
            raise ValueError("must contain Hebrew letters")
        return value


class CareGuide(SQLModel):
    """Care written into the catalog, whether curated or from the AI service."""

    model_config = ConfigDict(extra="forbid")

    watering_interval_days: int = Field(ge=1, le=60)
    sunlight: Sunlight
    care_en: list[Step] = Field(min_length=3, max_length=8)
    care_he: list[Step] = Field(min_length=3, max_length=8)

    @field_validator("care_he")
    @classmethod
    def hebrew_steps(cls, steps: list[str]) -> list[str]:
        if not all(has_hebrew(s) for s in steps):
            raise ValueError("every Hebrew step must contain Hebrew letters")
        return steps

    @field_validator("care_en")
    @classmethod
    def english_steps(cls, steps: list[str]) -> list[str]:
        if any(has_hebrew(s) for s in steps):
            raise ValueError("English steps must not contain Hebrew")
        return steps


# --- garden ------------------------------------------------------------------------
class GardenPlant(SQLModel, table=True):
    __tablename__ = "garden_plant"

    id: int | None = Field(default=None, primary_key=True)
    plant_id: int = Field(foreign_key="plant.id", index=True)
    nickname: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=100)
    watering_interval_days: int = Field(ge=1, le=60)
    # Timezone-aware UTC only: SQLModel stores datetimes as UTC and rejects naive ones.
    last_watered_at: datetime
    created_at: datetime


class GardenPhoto(SQLModel, table=True):
    __tablename__ = "garden_photo"

    garden_plant_id: int = Field(
        primary_key=True, foreign_key="garden_plant.id", ondelete="CASCADE"
    )
    jpeg: bytes


OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class GardenPlantCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    plant_id: int = Field(ge=1)
    nickname: OptionalText | None = None
    location: OptionalText | None = None
    watering_interval_days: int | None = Field(default=None, ge=1, le=60)


class GardenPlantUpdate(SQLModel):
    """PATCH body. Empty nickname/location clears it; a null interval is ignored."""

    model_config = ConfigDict(extra="forbid")

    nickname: OptionalText | None = None
    location: OptionalText | None = None
    watering_interval_days: int | None = Field(default=None, ge=1, le=60)


class GardenPlantPublic(SQLModel):
    id: int
    plant: PlantPublic
    nickname: str | None
    location: str | None
    watering_interval_days: int
    last_watered_at: datetime
    created_at: datetime
    next_watering_on: date
    days_until_watering: int  # negative = overdue
    has_photo: bool


# --- identification ----------------------------------------------------------------
class IdentifyCandidate(SQLModel):
    scientific_name: str
    name_en: str
    name_he: str
    confidence: float
    plant_id: int | None  # the catalog plant to add, if one matches
    matched_on: Literal["species", "genus"] | None


class IdentifyResponse(SQLModel):
    is_plant: bool
    model: str  # e.g. "demo" or "ollama:gemma4:e2b": say which model answered
    candidates: list[IdentifyCandidate]
