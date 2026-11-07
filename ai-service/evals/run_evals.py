"""Score the extractor on evals/cases.yaml and print a results table.

Default (AI_MODEL unset or "test"): a deterministic regex baseline stands in for
the model, so this runs offline, for free, through the same agent code path.
Label results from this mode as "regex baseline", never as model quality.

Free local model (Ollama running on this machine):
    AI_MODEL=ollama:<tag> OLLAMA_BASE_URL=http://localhost:11434/v1 \
        uv run python -m evals.run_evals
Hosted model (costs tokens):
    AI_MODEL=openai:<model-id> OPENAI_API_KEY=... uv run python -m evals.run_evals
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_evals import Dataset, increment_eval_metric
from pydantic_evals.evaluators import Evaluator, EvaluatorContext, IsInstance

from app.agent import LIMITS, URGENCY, Deps, extract_agent
from app.schemas import ItemExtraction

CASES = Path(__file__).with_name("cases.yaml")
MODEL = os.getenv("AI_MODEL", "test")


# --- evaluators: one small, explainable check each -----------------------------
@dataclass
class TitleMatches(Evaluator):
    """The expected key phrase is in the output title, and it is a title (short)."""

    def evaluate(self, ctx: EvaluatorContext) -> bool:
        title = ctx.output.title.lower()
        return ctx.expected_output.title.lower() in title and len(title) <= 60


@dataclass
class PriorityMatches(Evaluator):
    def evaluate(self, ctx: EvaluatorContext) -> bool:
        return ctx.output.priority == ctx.expected_output.priority


@dataclass
class TagOverlap(Evaluator):
    """Jaccard similarity of output and expected tag sets (0.0-1.0)."""

    def evaluate(self, ctx: EvaluatorContext) -> float:
        got, want = set(ctx.output.tags), set(ctx.expected_output.tags)
        if not got and not want:
            return 1.0
        return len(got & want) / len(got | want)


def load_dataset() -> Dataset[str, ItemExtraction, dict]:
    dataset = Dataset[str, ItemExtraction, dict].from_file(CASES)
    for evaluator in (
        IsInstance(type_name="ItemExtraction"),  # schema check
        TitleMatches(),  # domain quality
        PriorityMatches(),  # domain quality
        TagOverlap(),  # domain quality, as a score
    ):
        dataset.add_evaluator(evaluator)
    return dataset


# --- deterministic stand-in for a model -----------------------------------------
URGENCY_WORDS = re.compile(r"\b(" + "|".join(URGENCY) + r")\b", re.IGNORECASE)
TAG_HINTS = {
    "errand": ("buy", "pick up"),
    "work": ("report", "client", "team", "meeting"),
    "idea": ("idea",),
    "follow-up": ("call back", "follow up", "reply"),
    "personal": ("dentist", "passport", "doctor"),
}


def regex_baseline(text: str) -> dict:
    """A deliberately naive parser: the score a real model has to beat."""
    first, _, rest = text.partition(":") if ":" in text else text.partition("\n")
    hit = URGENCY_WORDS.search(text)
    lower = text.lower()
    return {
        "title": first.strip(" -#")[:200] or "Untitled",
        "description": rest.strip()[:5000],
        "priority": URGENCY[hit[1].lower()] if hit else 3,
        "tags": [
            tag for tag, hints in TAG_HINTS.items() if any(h in lower for h in hints)
        ],
    }


def baseline_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    prompt = next(p for p in messages[0].parts if isinstance(p, UserPromptPart))
    args = json.dumps(regex_baseline(str(prompt.content)))
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])


# --- the task under test: the real agent, same code path as POST /extract --------
async def extract(text: str) -> ItemExtraction:
    result = await extract_agent.run(text, deps=Deps(), usage_limits=LIMITS)
    usage = result.usage
    increment_eval_metric("requests", usage.requests)  # cost drivers,
    increment_eval_metric("tokens", usage.total_tokens)  # shown per case
    if usage.cost is not None:  # None when there is no pricing data (offline)
        increment_eval_metric("cost_usd", float(usage.cost))
    return result.output


def run(model: str = MODEL):
    """Score `model` on every case. "test" means the offline regex baseline."""
    offline = model == "test"
    stand_in = FunctionModel(baseline_model) if offline else model
    with extract_agent.override(model=stand_in):
        return load_dataset().evaluate_sync(
            extract,
            name="regex-baseline" if offline else model,
            progress=False,
            max_concurrency=2,  # be gentle with provider rate limits
        )


if __name__ == "__main__":
    report = run()
    # Durations vary from run to run: hide them for the deterministic baseline.
    report.print(width=100, include_durations=MODEL != "test")
