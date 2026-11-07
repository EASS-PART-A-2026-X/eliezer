"""Backend -> ai-service client: explicit timeouts, typed errors, bounded retries.

Retry policy (one layer only, here):
- Retried (at most 3 attempts, with backoff): nothing reached the ai-service
  (connection refused / connect timeout) or it answered 503 (busy, not started).
- NOT retried: a read timeout or a 504. The model runs on a CPU and may take a
  minute; work that timed out once will time out again and only loads a
  saturated machine further (course: Lecture 9 allows dropping 504 retries for
  slow generation; local-inference guide warns against blind retries).
"""

import base64
import os
from collections.abc import Iterator
from typing import Annotated, Literal

import httpx
from fastapi import Depends
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.models import CareGuide

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001")

# Read timeouts sit above the ai-service's own wall-clock caps (150 s / 200 s),
# so the ai-service answers 504 itself instead of us cutting it off.
IDENTIFY_TIMEOUT = httpx.Timeout(connect=2.0, read=170.0, write=10.0, pool=2.0)
CARE_TIMEOUT = httpx.Timeout(connect=2.0, read=220.0, write=5.0, pool=2.0)

Text120 = Annotated[str, Field(min_length=1, max_length=120)]
CareStep = Annotated[str, Field(min_length=1, max_length=300)]


# --- the ai-service contract (tests/test_contract.py checks it against theirs) -----
class IdentifyRequest(BaseModel):
    image_b64: str = Field(min_length=1, max_length=8_000_000)
    media_type: Literal["image/jpeg", "image/png", "image/webp"]


class Candidate(BaseModel):
    scientific_name: Text120
    name_en: Text120
    name_he: Text120
    confidence: float = Field(ge=0, le=1)


class PlantIdentification(BaseModel):
    is_plant: bool
    model: str = Field(min_length=1, max_length=100)
    candidates: list[Candidate] = Field(max_length=3)


class CareRequest(BaseModel):
    scientific_name: Text120
    name_en: Text120
    name_he: Text120


class CareGuideOut(BaseModel):
    watering_interval_days: int = Field(ge=1, le=60)
    sunlight: Literal["full_sun", "partial_shade", "shade"]
    care_en: list[CareStep] = Field(min_length=3, max_length=8)
    care_he: list[CareStep] = Field(min_length=3, max_length=8)


# --- errors ---------------------------------------------------------------------------
class AIServiceUnavailable(Exception):
    """ai-service unreachable, timing out, over budget, or failing with a 5xx."""


class AIServiceBadOutput(Exception):
    """ai-service answered, but not with something we can use."""


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return True  # the request never reached the ai-service
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 503


class AIClient:
    def __init__(
        self,
        base_url: str = AI_SERVICE_URL,
        transport: httpx.BaseTransport | None = None,  # tests pass MockTransport
    ) -> None:
        self._http = httpx.Client(base_url=base_url, transport=transport)

    def close(self) -> None:
        self._http.close()

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(3),  # bounded: 1 try + 2 retries
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,  # give up with the real httpx error, not RetryError
    )
    def _post(self, path: str, body: dict, timeout: httpx.Timeout) -> httpx.Response:
        response = self._http.post(path, json=body, timeout=timeout)
        response.raise_for_status()
        return response

    def _call(self, path: str, body: dict, timeout: httpx.Timeout) -> httpx.Response:
        try:
            return self._post(path, body, timeout)
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            # 502: output still invalid after the agent's retries; 4xx: our bug.
            if code == 502 or (code < 500 and code != 429):
                raise AIServiceBadOutput(f"ai-service returned {code}") from exc
            # 429 (AI budget spent), 500, 504, or 503 after our retries.
            raise AIServiceUnavailable(f"ai-service returned {code}") from exc
        except httpx.HTTPError as exc:  # timeouts, refused connections, DNS
            raise AIServiceUnavailable(f"ai-service unreachable: {exc!r}") from exc

    def identify(self, jpeg: bytes) -> PlantIdentification:
        body = IdentifyRequest(
            image_b64=base64.b64encode(jpeg).decode("ascii"), media_type="image/jpeg"
        )
        response = self._call("/identify", body.model_dump(), IDENTIFY_TIMEOUT)
        try:
            return PlantIdentification.model_validate_json(response.content)
        except ValidationError as exc:
            raise AIServiceBadOutput("ai-service response broke the contract") from exc

    def write_care(self, scientific_name: str, name_en: str, name_he: str) -> CareGuide:
        body = CareRequest(
            scientific_name=scientific_name, name_en=name_en, name_he=name_he
        )
        response = self._call("/care", body.model_dump(), CARE_TIMEOUT)
        try:
            guide = CareGuideOut.model_validate_json(response.content)
            # Our own rules on top of theirs (e.g. Hebrew steps really are Hebrew).
            return CareGuide.model_validate(guide.model_dump())
        except ValidationError as exc:
            raise AIServiceBadOutput("ai-service response broke the contract") from exc


def get_ai_client() -> Iterator[AIClient]:
    client = AIClient()
    try:
        yield client
    finally:
        client.close()


AIClientDep = Annotated[AIClient, Depends(get_ai_client)]
