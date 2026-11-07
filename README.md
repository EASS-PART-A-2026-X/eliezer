# eliezer

> **Boilerplate status:** the record (`Item`: title, description, priority, tags) and the AI job (free text → structured item) are placeholders. Replace them with your domain. See [Adapting the placeholder domain](#adapting-the-placeholder-domain) and [REQUIREMENTS.md](REQUIREMENTS.md).

One sentence: who it is for and what problem it solves. **TODO**

**Purpose:** the need, and the bad situation it prevents. **TODO**
**Operational principle:** after *someone* does *A*, then *B*; afterwards *C* holds. **TODO**

## User stories

1. As a *user*, I can *action* so that *benefit*. **TODO**
2. **TODO**
3. **TODO**

## Data sketch

`Item`: `title` (text, 1–200 chars), `description` (text, ≤5000 chars), `priority` (integer 1–5, default 3), `tags` (text, ≤500 chars, comma-separated).

## The AI service

Input: free text (1–5000 chars). Structured output: `ItemExtraction` (`title`, `description`, `priority`, `tags` limited to an allowed list).

## Data flow

```text
browser
  -> frontend    (Streamlit)               :8501
  -> backend     (FastAPI + Pydantic)      :8000  -> SQLite (only the backend)
  -> ai-service  (FastAPI + Pydantic AI)   :8001  (called only by the backend; not published)
```

Only the backend reads or writes the database. The frontend never calls the AI service, and the AI service never opens the database: it returns a candidate that the backend validates before saving.

---

## Setup

Requirements: Docker with Compose v2, [uv](https://docs.astral.sh/uv/) (for local runs and tests), Python 3.14 (uv can install it).

```bash
cp .env.example .env   # optional: the stack also starts without it
```

| Setting | Where | Default | Meaning |
|---|---|---|---|
| `AI_MODEL` | `.env` | `test` | `test` = Pydantic AI TestModel (no key, no cost); or `<provider>:<model>` |
| `BACKEND_PORT` / `FRONTEND_PORT` | `.env` | `8000` / `8501` | host ports, if the defaults are taken |
| `DATABASE_URL` | backend env | `sqlite:///./data/app.db` locally; `sqlite:////app/data/app.db` in Compose | where SQLite lives |
| `AI_SERVICE_URL` | backend env | `http://localhost:8001` locally; `http://ai-service:8001` in Compose | how the backend reaches the AI service |
| `BACKEND_URL` | frontend env | `http://localhost:8000` locally; `http://backend:8000` in Compose | how the frontend reaches the backend |

## Run

```bash
docker compose up --build --wait
```

- UI: <http://localhost:8501> · API docs: <http://localhost:8000/docs> · health: <http://localhost:8000/health>
- `docker compose down` stops the stack and **keeps** the data.
- `docker compose down -v` **deletes** the data. The next start reseeds the demo rows.
- The data lives in the `backend-data` volume at `/app/data`. Optional backup: `docker compose cp backend:/app/data/app.db backup.db`

### Run without Docker (development)

Use three terminals:

```bash
cd ai-service && uv run fastapi dev --port 8001
cd backend    && uv run fastapi dev            # port 8000, data in backend/data/
cd frontend   && uv run streamlit run streamlit_app.py
```

## Test

Every command runs offline, with no API key and no model calls.

| Service | Command (from the service folder) | What it covers |
|---|---|---|
| backend | `uv run pytest` | CRUD and status codes, validation limits, restart persistence, seed, AI client retries and error mapping, contract |
| ai-service | `uv run pytest` | agent tools and validator, 422/429/500/502/504 mapping, no user text in logs, eval harness |
| frontend | `uv run pytest` | AppTest flows: empty, backend down, 422 in words, lost reply, AI errors; UI → `api.py` boundary |
| frontend (browser) | `uv run pytest e2e --base-url http://localhost:8501 --browser-channel chrome` | one real-browser flow; needs the running stack. Without Chrome, run `uv run playwright install chromium` and drop `--browser-channel chrome` |
| lint (each service) | `uv run ruff check . && uv run ruff format --check .` | |
| evaluation | `uv run python -m evals.run_evals` (in `ai-service/`) | results table; see [Evaluation results](#evaluation-results) |
| whole repo | `scripts/clean-checkout.sh` (repo root, committed work only) | what a grader does: fresh clone → Compose → smoke test → all tests |

**Contract snapshot.** After any change to the AI service's schemas, regenerate the snapshot, then run the backend tests:

```bash
cd ai-service
uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > ../backend/tests/ai_openapi.json
```

### AI contract

| Call | Request | Success | Failures |
|---|---|---|---|
| backend `POST /items/from-text` | `{"text": str 1–5000}` | `201` saved item | `422` invalid text (no AI call) · `503` AI down, timed out, 5xx or over budget · `502` AI output broke the contract |
| ai-service `POST /extract` | `{"text": str 1–5000}` | `200` `ItemExtraction` | `422` invalid · `429` usage limit · `502` invalid output after retries · `504` model timeout · `500` provider failed |

Retries live in one layer, the backend: timeouts, connection errors, 503 and 504 get at most 3 attempts with backoff. Everything else gets a single try.

## Failure drills

| What you stop or break | What the user sees | Recover |
|---|---|---|
| `docker compose stop ai-service` | AI tab: "AI service is unavailable, try again in a minute." The other tabs still work. The API returns `503` in about 2 s | `docker compose up --wait` |
| `docker compose stop backend` | "Cannot reach the backend at …. Start it (docker compose up) and reload the page." | `docker compose up --wait`, then reload |
| invalid input (e.g. priority 0 via the API) | "Please fix: priority: …" | correct the field |
| reply lost after a write | "Your change may have been saved. Reload the page and check before trying again." | reload and check |

## Real-model run (optional)

Automated tests never call a real model. To try one, set `AI_MODEL` in `.env`:

- Free and local: `AI_MODEL=ollama:<model>` and `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1`. Ollama must listen where Docker can reach it.
- Hosted (costs money): `AI_MODEL=openai:<model-id>` plus `OPENAI_API_KEY=...`.

Per-request caps (`app/agent.py`): at most 5 model requests, 5 tool calls and 20,000 tokens.

### Evaluation results

| Date | Model / configuration | Cases | Assertions passed | TagOverlap (avg) | Notes |
|---|---|---|---|---|---|
| 2026-11-07 | regex baseline (`AI_MODEL=test`, no model) | 8 | 79.2% | 0.938 | Deterministic stand-in, **not** model quality. Placeholder dataset |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `port is already allocated` | 8000 or 8501 is in use | set `BACKEND_PORT` / `FRONTEND_PORT` in `.env` |
| every AI request returns 502 after a schema change | the contract drifted | regenerate `ai_openapi.json` and run the backend tests |
| AI items have placeholder titles like `"a"` | `AI_MODEL=test` (TestModel) | expected. Set a real model for real output |

## Demo video

**TODO:** link to the English-narrated demo of `v1.0.0` (must play without signing in).

## AI-use note

Tools: **TODO** · Help received: **TODO** · Checks I ran: **TODO**

## Open-source evidence

| Student (GitHub handle) | Official repository | License URL | Stars (date checked) | PR URL | Contribution summary | Merge evidence (main branch) |
|---|---|---|---|---|---|---|
| | | | | | | |

---

## Adapting the placeholder domain

Rename `Item` and its fields in these places, then run every service's tests:

1. `backend/app/models.py`: the table, Create/Update/Public models and their limits
2. `backend/app/seed.py`: synthetic demo rows
3. `backend/app/ai_client.py`: `ItemExtraction` (the backend's copy of the contract) and `extract_item`
4. `backend/app/main.py`: route paths (`/items`) and names
5. `ai-service/app/schemas.py` and `ai-service/app/agent.py`: output model, instructions, tools, validator
6. `ai-service/evals/cases.yaml` and the evaluators in `ai-service/evals/run_evals.py`
7. `frontend/api.py` (`Item` TypedDict, paths) and `frontend/streamlit_app.py` (form fields, labels)
8. Every service's tests, `frontend/e2e/test_e2e.py`, the smoke test in `.github/workflows/ci.yml` and `scripts/clean-checkout.sh`
9. Regenerate `backend/tests/ai_openapi.json`
