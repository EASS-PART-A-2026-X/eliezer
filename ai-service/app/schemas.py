"""The ai-service contract. The backend keeps a copy (backend/app/ai_client.py);
backend/tests/test_contract.py fails if the two drift apart.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Text120 = Annotated[str, Field(min_length=1, max_length=120)]
Step = Annotated[str, Field(min_length=1, max_length=300)]
Sunlight = Literal["full_sun", "partial_shade", "shade"]


# --- POST /identify ----------------------------------------------------------------
class IdentifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_b64: str = Field(min_length=1, max_length=8_000_000)
    media_type: Literal["image/jpeg", "image/png", "image/webp"]


class Candidate(BaseModel):
    """One possible species for the plant in the photo."""

    # Docstrings and descriptions are model-facing: they go into the schema the
    # model is asked to fill. Keep developer notes in comments like this one.
    scientific_name: Text120 = Field(
        description="Accepted Latin name, e.g. 'Salvia rosmarinus'"
    )
    name_en: Text120 = Field(description="Common English name")
    name_he: Text120 = Field(description="Common Hebrew name, in Hebrew letters")
    confidence: float = Field(ge=0, le=1, description="0 to 1; most likely first")


class IdentificationOutput(BaseModel):
    """What the photo shows: up to three candidate species, most likely first."""

    is_plant: bool = Field(description="False if the photo does not show a plant")
    candidates: list[Candidate] = Field(max_length=3)


class PlantIdentification(IdentificationOutput):
    """The /identify response: the model's answer plus which model gave it."""

    model: str = Field(min_length=1, max_length=100)


# --- POST /care ----------------------------------------------------------------------
class CareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scientific_name: Text120
    name_en: Text120
    name_he: Text120


class CareGuide(BaseModel):
    """Short, practical care instructions for one plant, in English and Hebrew."""

    watering_interval_days: int = Field(
        ge=1, le=60, description="Typical days between waterings this season"
    )
    sunlight: Sunlight
    care_en: list[Step] = Field(
        min_length=3, max_length=8, description="Steps in English"
    )
    care_he: list[Step] = Field(
        min_length=3, max_length=8, description="The same steps in Hebrew"
    )
