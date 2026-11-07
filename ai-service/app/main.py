import asyncio
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic_ai import (
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)

from app.agent import LIMITS, Deps, extract_agent
from app.schemas import ExtractRequest, ItemExtraction

logger = logging.getLogger("ai-service")

# Wall-clock cap per request; keep it below the backend's 30 s read timeout.
MODEL_TIMEOUT_SECONDS = 25.0

app = FastAPI(title="eliezer AI service")


def get_deps() -> Deps:
    return Deps()


DepsDep = Annotated[Deps, Depends(get_deps)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/extract")
async def extract(body: ExtractRequest, deps: DepsDep) -> ItemExtraction:
    try:
        async with asyncio.timeout(MODEL_TIMEOUT_SECONDS):
            result = await extract_agent.run(body.text, deps=deps, usage_limits=LIMITS)
    except UsageLimitExceeded as exc:  # 429 is our contract's budget signal
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, detail="AI budget exceeded"
        ) from exc
    except UnexpectedModelBehavior as exc:  # still invalid after the agent's retries
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="AI returned invalid output"
        ) from exc
    except ModelHTTPError as exc:  # provider answered 4xx/5xx; its SDK retried
        logger.warning("model provider error: status_code=%d", exc.status_code)
        if exc.status_code in (401, 403):  # bad key or no access: fix the config
            detail = "AI model misconfigured"
        else:
            detail = "AI provider failed"
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        ) from exc
    except ModelAPIError as exc:  # no answer at all, e.g. Ollama is not running
        logger.warning("model provider unreachable: %s", exc.model_name)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI provider failed"
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT, detail="AI model timed out"
        ) from exc
    usage = result.usage
    # Log cost drivers, never the user's text.
    logger.info(
        "extract ok: requests=%d total_tokens=%d", usage.requests, usage.total_tokens
    )
    return result.output
