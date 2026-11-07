"""Backend -> ai-service client: explicit timeouts, typed errors, bounded retries.

Retries live in ONE layer, here. The agent inside the ai-service already
retries the model, so only "unreachable", "timed out", 503 and 504 are retried.
"""

import os
from collections.abc import Iterator
from typing import Annotated

import httpx
from fastapi import Depends
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.models import ItemCreate

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001")

# Every outbound call gets a timeout per phase. Connect fast; let the model think.
TIMEOUT = httpx.Timeout(connect=2.0, read=30.0, write=5.0, pool=2.0)
TRANSIENT_STATUS = {503, 504}


class ItemExtraction(BaseModel):
    """The ai-service contract: what POST /extract must return.

    tests/test_contract.py checks this against the ai-service's published schema.
    """

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    priority: int = Field(default=3, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)


class AIServiceUnavailable(Exception):
    """ai-service unreachable, timing out, over budget, or failing with a 5xx."""


class AIServiceBadOutput(Exception):
    """ai-service answered, but not with something we can use."""


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in TRANSIENT_STATUS
    )


class AIClient:
    def __init__(
        self,
        base_url: str = AI_SERVICE_URL,
        transport: httpx.BaseTransport | None = None,  # tests pass MockTransport
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url, timeout=TIMEOUT, transport=transport
        )

    def close(self) -> None:
        self._http.close()

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(3),  # bounded: 1 try + 2 retries
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,  # give up with the real httpx error, not RetryError
    )
    def _post_extract(self, text: str) -> httpx.Response:
        response = self._http.post("/extract", json={"text": text})
        response.raise_for_status()
        return response

    def extract_item(self, text: str) -> ItemCreate:
        try:
            response = self._post_extract(text)
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            # 502: output still invalid after the agent's retries; 4xx: our bug.
            if code == 502 or (code < 500 and code != 429):
                raise AIServiceBadOutput(f"ai-service returned {code}") from exc
            # 429 (AI budget spent), 500, or 503/504 after our retries.
            raise AIServiceUnavailable(f"ai-service returned {code}") from exc
        except httpx.HTTPError as exc:  # timeouts, refused connections, DNS
            raise AIServiceUnavailable(f"ai-service unreachable: {exc!r}") from exc
        try:
            extraction = ItemExtraction.model_validate_json(response.content)
            # Translate their contract into our model (and validate it again).
            return ItemCreate(
                title=extraction.title,
                description=extraction.description,
                priority=extraction.priority,
                tags=",".join(extraction.tags),
            )
        except ValidationError as exc:
            raise AIServiceBadOutput("ai-service response broke the contract") from exc


def get_ai_client() -> Iterator[AIClient]:
    client = AIClient()
    try:
        yield client
    finally:
        client.close()


AIClientDep = Annotated[AIClient, Depends(get_ai_client)]
