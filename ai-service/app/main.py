import asyncio
import base64
import binascii
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic_ai import (
    Agent,
    BinaryContent,
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
    UsageLimits,
    UserError,
)

from app.agents import (
    CARE_LIMITS,
    IDENTIFY_LIMITS,
    MODEL_LABEL,
    Deps,
    care_agent,
    identify_agent,
)
from app.schemas import CareGuide, CareRequest, IdentifyRequest, PlantIdentification

logger = logging.getLogger("ai-service")

# Wall-clock caps; the backend's read timeouts (170 s / 220 s) sit above these.
IDENTIFY_TIMEOUT_SECONDS = 150.0
CARE_TIMEOUT_SECONDS = 200.0

# The first bytes of each allowed image format.
SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}

app = FastAPI(title="Eliezer AI service")


def get_deps() -> Deps:
    return Deps()


DepsDep = Annotated[Deps, Depends(get_deps)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def run_agent(
    agent: Agent, prompt, deps: Deps, limits: UsageLimits, timeout: float, task: str
):
    try:
        async with asyncio.timeout(timeout):
            result = await agent.run(prompt, deps=deps, usage_limits=limits)
    except UsageLimitExceeded as exc:  # 429 is our contract's budget signal
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, detail="AI budget exceeded"
        ) from exc
    except UnexpectedModelBehavior as exc:  # still invalid after the agent's retries
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="AI returned invalid output"
        ) from exc
    except ModelHTTPError as exc:  # provider answered 4xx/5xx
        logger.warning("%s: model provider error status_code=%d", task, exc.status_code)
        detail = (
            "AI model misconfigured"
            if exc.status_code in (401, 403, 404)
            else "AI provider failed"
        )
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        ) from exc
    except ModelAPIError as exc:  # no answer at all, e.g. Ollama is not running
        logger.warning("%s: model provider unreachable: %s", task, exc.model_name)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI provider failed"
        ) from exc
    except UserError as exc:  # e.g. OLLAMA_BASE_URL missing
        logger.warning("%s: model configuration error: %s", task, exc)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI model misconfigured"
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT, detail="AI model timed out"
        ) from exc
    usage = result.usage
    # Log cost drivers, never the user's photo or text.
    logger.info(
        "%s ok: model=%s requests=%d total_tokens=%d",
        task,
        MODEL_LABEL,
        usage.requests,
        usage.total_tokens,
    )
    return result.output


def decode_image(body: IdentifyRequest) -> bytes:
    try:
        data = base64.b64decode(body.image_b64, validate=True)
    except binascii.Error:
        data = b""
    if not data.startswith(SIGNATURES[body.media_type]):
        detail = [
            {
                "loc": ["body", "image_b64"],
                "msg": f"not valid base64 {body.media_type} data",
                "type": "invalid_image",
            }
        ]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)
    return data


@app.post("/identify")
async def identify(body: IdentifyRequest, deps: DepsDep) -> PlantIdentification:
    image = BinaryContent(data=decode_image(body), media_type=body.media_type)
    output = await run_agent(
        identify_agent,
        ["Identify the plant in this photo.", image],
        deps,
        IDENTIFY_LIMITS,
        IDENTIFY_TIMEOUT_SECONDS,
        "identify",
    )
    return PlantIdentification(
        is_plant=output.is_plant,
        candidates=output.candidates if output.is_plant else [],
        model=MODEL_LABEL,
    )


@app.post("/care")
async def care(body: CareRequest, deps: DepsDep) -> CareGuide:
    prompt = (
        f"Plant: {body.scientific_name} "
        f"(English name: {body.name_en}; Hebrew name: {body.name_he})."
    )
    return await run_agent(
        care_agent, prompt, deps, CARE_LIMITS, CARE_TIMEOUT_SECONDS, "care"
    )
