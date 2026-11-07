"""Score plant identification on evals/cases.yaml and print a results table.

Default (AI_MODEL unset or "test"): a fixed-answer baseline (always "rosemary")
stands in for the model, so this runs offline, for free, through the same agent
code path. Label those results "fixed-answer baseline", never model quality.

Local Gemma 4 through Ollama (Ollama >= 0.20.6 running, model pulled):
    AI_MODEL=ollama:gemma4:e2b OLLAMA_BASE_URL=http://localhost:11434/v1 \
        uv run python -m evals.run_evals
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import BinaryContent
from pydantic_evals import Dataset, increment_eval_metric
from pydantic_evals.evaluators import Evaluator, EvaluatorContext, IsInstance

from app.agents import (
    DEMO_IDENTIFICATION,
    HEBREW,
    IDENTIFY_LIMITS,
    Deps,
    fixed_json_model,
    identify_agent,
)
from app.schemas import IdentificationOutput

HERE = Path(__file__).parent
CASES = HERE / "cases.yaml"
IMAGES = HERE / "images"
MODEL = os.getenv("AI_MODEL", "test")


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace("×", " ")).strip().lower()


def same_taxon(expected: str, got: str) -> bool:
    """A one-word expected name is a genus: then the genus is enough."""
    e, g = normalize(expected), normalize(got)
    return g.split(" ")[0] == e if " " not in e else g == e


# --- evaluators: one small, explainable check each -----------------------------
@dataclass
class PlantDecision(Evaluator):
    """Control flow: is_plant matches, and a non-plant gets no candidates."""

    def evaluate(self, ctx: EvaluatorContext) -> bool:
        if not ctx.metadata["is_plant"]:
            return not ctx.output.is_plant and not ctx.output.candidates
        return ctx.output.is_plant


@dataclass
class Top1Species(Evaluator):
    def evaluate(self, ctx: EvaluatorContext) -> bool:
        if not ctx.metadata["is_plant"]:
            return not ctx.output.candidates
        if not ctx.output.candidates:
            return False
        top = ctx.output.candidates[0].scientific_name
        return any(same_taxon(name, top) for name in ctx.metadata["names"])


@dataclass
class InTop3(Evaluator):
    def evaluate(self, ctx: EvaluatorContext) -> bool:
        if not ctx.metadata["is_plant"]:
            return not ctx.output.candidates
        return any(
            same_taxon(name, c.scientific_name)
            for c in ctx.output.candidates
            for name in ctx.metadata["names"]
        )


@dataclass
class GenusMatch(Evaluator):
    """Score: 1.0 if the top candidate's genus is right (partial credit)."""

    def evaluate(self, ctx: EvaluatorContext) -> float:
        if not ctx.metadata["is_plant"]:
            return 1.0 if not ctx.output.candidates else 0.0
        if not ctx.output.candidates:
            return 0.0
        genus = normalize(ctx.output.candidates[0].scientific_name).split(" ")[0]
        expected = {normalize(n).split(" ")[0] for n in ctx.metadata["names"]}
        return 1.0 if genus in expected else 0.0


@dataclass
class HebrewNames(Evaluator):
    def evaluate(self, ctx: EvaluatorContext) -> bool:
        return all(HEBREW.search(c.name_he) for c in ctx.output.candidates)


def load_dataset() -> Dataset[str, IdentificationOutput, dict]:
    dataset = Dataset[str, IdentificationOutput, dict].from_file(CASES)
    for evaluator in (
        IsInstance(type_name="IdentificationOutput"),  # schema
        PlantDecision(),  # control flow
        Top1Species(),  # domain quality
        InTop3(),  # domain quality
        GenusMatch(),  # domain quality, as a score
        HebrewNames(),  # language requirement
    ):
        dataset.add_evaluator(evaluator)
    return dataset


# --- the task under test: the real agent, same code path as POST /identify ----------
async def identify(image_file: str) -> IdentificationOutput:
    image = BinaryContent(
        data=(IMAGES / image_file).read_bytes(), media_type="image/jpeg"
    )
    result = await identify_agent.run(
        ["Identify the plant in this photo.", image],
        deps=Deps(),
        usage_limits=IDENTIFY_LIMITS,
    )
    usage = result.usage
    increment_eval_metric("requests", usage.requests)  # cost drivers,
    increment_eval_metric("tokens", usage.total_tokens)  # shown per case
    return result.output


def run(model: str = MODEL):
    """Score `model` on every case. "test" means the offline fixed-answer baseline."""
    offline = model == "test"
    stand_in = (
        fixed_json_model(DEMO_IDENTIFICATION.model_dump_json()) if offline else model
    )
    with identify_agent.override(model=stand_in):
        return load_dataset().evaluate_sync(
            identify,
            name="fixed-answer-baseline" if offline else model,
            progress=False,
            max_concurrency=1,  # one CPU model: run cases one after another
        )


if __name__ == "__main__":
    report = run()
    # Durations vary from run to run: hide them for the deterministic baseline.
    report.print(width=110, include_durations=MODEL != "test")
