# Eliezer — your garden master · אליעזר — מאסטר הגינה שלך

Eliezer helps home gardeners in Israel keep every plant alive: identify a plant from a photo, get care instructions in Hebrew or English, and see at a glance which plants need water today.

**Purpose:** plants die because nobody remembers when each one was last watered or what it needs. Care advice is scattered, often only in English, and you can't look it up if you don't know the plant's name.

**Operational principle:** after I photograph a plant and confirm what Eliezer identified, it appears in my garden with a watering countdown and care steps; after I press "I watered it", the countdown starts again, and it is still there tomorrow.

## User stories

1. As a gardener, I can photograph a plant I don't know so that Eliezer tells me what it is and how to care for it.
2. As a gardener, I can add a plant by its name in Hebrew, English or Latin so that I don't need a photo for plants I already know.
3. As a gardener, I can see how many days are left until each plant needs water, and mark it as watered, so that nothing dries out.
4. As a Hebrew speaker, I can switch the whole interface to Hebrew (right-to-left) so that I can use it in my own language.

## Data sketch

- **Plant** (catalog, ~1,500 rows): `scientific_name` (unique, ≤120), `name_en`, `name_he` (≤120), `watering_interval_days` (1–60, optional), `sunlight` (full_sun / partial_shade / shade), `care_en`, `care_he` (3–8 steps of ≤300 chars), `care_source` (curated / ai / none).
- **GardenPlant** (your garden): `plant_id`, `nickname`, `location` (≤100, optional), `watering_interval_days` (1–60), `last_watered_at`, `created_at`. Computed: `next_watering_on`, `days_until_watering` (negative = overdue), using Israel calendar days.
- **GardenPhoto**: an optional JPEG thumbnail (≤512 px, metadata stripped) per garden plant.

## The AI service

Two jobs, both with structured, validated output:

- **Identify** — input: one photo. Output: `is_plant` plus up to 3 candidates (`scientific_name`, `name_en`, `name_he`, `confidence`). The backend matches each candidate to the catalog; the user confirms one.
- **Care** — input: a plant's names. Output: watering interval, sunlight, and 3–8 care steps in English and in Hebrew. Written once per plant, validated, then stored in the catalog.

Real model: **Gemma 4 E2B** (`gemma4:e2b`) on a local Ollama. It reads images and writes Hebrew, and fits a laptop without a GPU. Llama 3.2 Vision was rejected: no official Hebrew support, and larger. Vision models are often wrong about species, which is why the user always confirms a candidate or searches by name.

## Data flow

```text
browser
  -> frontend    (Streamlit)               :8501
  -> backend     (FastAPI + Pydantic)      :8000  -> PostgreSQL "db" (only the backend)
  -> ai-service  (FastAPI + Pydantic AI)   :8001  (called only by the backend; not published)
                                                   -> Ollama on the host (optional real model)
```

Only the backend reads or writes the database. The frontend never calls the AI service or the database, and the AI service never opens the database: it returns candidates that the backend validates before anything is saved. PostgreSQL and Ollama are infrastructure, not application services.

**Why Streamlit:** one language (Python) across all three services and the course's tested patterns; the cost is less layout control, so right-to-left Hebrew, the card grid and tap-to-open cards are done with injected CSS (`frontend/style.py`), aimed at the `st-key-*` classes Streamlit gives keyed elements. Theme colours (green, orange, white) live in `frontend/.streamlit/config.toml`.

---

## Setup

Requirements: Docker with Compose v2; [uv](https://docs.astral.sh/uv/) for local runs and tests (Python 3.14).

```bash
cp .env.example .env   # optional: the stack also starts without it (demo mode)
```

| Setting | Where | Default | Meaning |
|---|---|---|---|
| `POSTGRES_PASSWORD` | `.env` | `eliezer-dev` | password of the `db` service; set your own |
| `AI_MODEL` | `.env` | `test` | `test` = **demo mode** (fixed stand-in answers, no key, no cost); `ollama:gemma4:e2b` = real model |
| `OLLAMA_BASE_URL` | `.env` | `http://host.docker.internal:11434/v1` | where the ai-service finds Ollama |
| `GARDEN_REGION` | `.env` | `Israel (Mediterranean climate)` | region used in the AI instructions |
| `BACKEND_PORT` / `FRONTEND_PORT` | `.env` | `8000` / `8501` | host ports, if the defaults are taken |
| `DATABASE_URL` | backend | Compose: Postgres; image/local default: `sqlite:///./data/app.db` | where data lives |
| `AI_SERVICE_URL` / `BACKEND_URL` | backend / frontend | Compose service names | how services find each other |

## Run

```bash
docker compose up --build --wait
```

- App: <http://localhost:8501> · API docs: <http://localhost:8000/docs> · health: <http://localhost:8000/health>
- The first start loads the plant catalog (~1,500 plants) and a 3-plant demo garden; the backend logs `seeded … catalog plants`.
- `docker compose down` stops everything and **keeps** your data (the `db-data` volume).
- `docker compose down -v` **deletes** your garden and the AI-written care. The next start reloads the catalog and demo garden.
- Backup: `docker compose exec db pg_dump -U eliezer eliezer > backup.sql` · restore into a fresh stack: `docker compose exec -T db psql -U eliezer eliezer < backup.sql`

### Run the backend alone (EX1 check, SQLite)

The backend image defaults to SQLite in `/app/data`, so it also runs without Compose:

```bash
cd backend
docker build -t eliezer-backend .
docker run -d --name backend -p 127.0.0.1:8000:8000 -v backend-data:/app/data eliezer-backend
curl -sS --retry 10 --retry-all-errors --retry-delay 1 localhost:8000/health
```

### Run without Docker (development)

```bash
cd ai-service && uv run fastapi dev --port 8001
cd backend    && uv run fastapi dev            # SQLite in backend/data/
cd frontend   && uv run streamlit run streamlit_app.py
```

## Test

Every command runs offline, with no API key and no model calls.

| Service | Command (from the service folder) | What it covers |
|---|---|---|
| backend | `uv run pytest` | catalog search (EN/HE/Latin), status codes, garden countdown with a frozen clock, watering, photos and upload checks, identify matching, retry policy, AI care validated and stored, restart persistence, seed, catalog files, contract |
| ai-service | `uv run pytest` | demo mode, identify and care validators (each forces a retry), 422/429/500/502/504 mapping, tools, no photo or text in logs, eval harness |
| frontend | `uv run pytest` | AppTest flows in both languages: plant cards (photo or placeholder) open a details modal, RTL CSS, watering, care request, adding a photo later, remove with confirmation, identify → add (including new catalog plants), one-tap search → add, friendly errors, lost reply; UI → `api.py` boundary; i18n keys and placeholders |
| frontend (browser) | `uv run pytest e2e --base-url http://localhost:8501 --browser-channel chrome` | needs the running stack: search → add → details modal → nickname → reload → tap the card → water → remove; Hebrew toggle → RTL; phone width shows 2 cards per row with no sideways scrolling. Without Chrome: `uv run playwright install chromium` and drop `--browser-channel chrome` |
| lint (each service) | `uv run ruff check . && uv run ruff format --check .` | |
| evaluation | `uv run python -m evals.run_evals` (in `ai-service/`) | see [Evaluation results](#evaluation-results) |
| whole repo | `scripts/clean-checkout.sh` (repo root, committed work only) | fresh clone → Compose → smoke test → all tests |

**Contract snapshot.** After any change to the ai-service schemas:

```bash
cd ai-service
uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > ../backend/tests/ai_openapi.json
```

### API

| Method + path | Purpose |
|---|---|
| `GET /plants?q=&offset=&limit=` | search the catalog by English, Hebrew or Latin name (curated plants first) |
| `GET /plants/{id}` · `POST /plants` | one plant · add an identified plant missing from the catalog (409 if it exists) |
| `POST /plants/{id}/care` | return care; the first time, the AI writes it, the backend validates and stores it |
| `POST /plants/identify` | photo → up to 3 candidates matched to the catalog (saves nothing) |
| `GET /garden` · `POST /garden` | my plants sorted by days left · add a catalog plant |
| `GET` · `PATCH` · `DELETE /garden/{id}` | one plant · edit nickname/location/interval · remove |
| `POST /garden/{id}/water` | mark watered now: the countdown restarts |
| `PUT` · `GET /garden/{id}/photo` | store · fetch the thumbnail |

### AI contract

| Call | Request | Success | Failures |
|---|---|---|---|
| backend `POST /plants/identify` | multipart `photo` (JPEG/PNG/WebP, ≤5 MB) | `200` candidates | `422` bad photo (no AI call) · `503` AI down, timed out, over budget or 5xx · `502` AI output broke the contract |
| backend `POST /plants/{id}/care` | — | `200` plant with care | `404` · `503` · `502` (nothing stored) |
| ai-service `POST /identify` | `{image_b64, media_type}` | `200` `PlantIdentification` (+ `model`) | `422` · `429` usage limit · `502` invalid after retries · `504` timeout (150 s) · `500` provider failed or misconfigured |
| ai-service `POST /care` | `{scientific_name, name_en, name_he}` | `200` `CareGuide` | same as above (timeout 200 s) |

**Retry policy** (one layer, the backend): a request that never reached the ai-service (connection refused, connect timeout) or got `503` is retried, at most 3 attempts with backoff. A read timeout or `504` is **not** retried: the model runs on a CPU, and work that timed out once will time out again while loading the machine further (Lecture 9 allows dropping 504 retries for slow generation). Timeouts nest: ai-service caps (150 / 200 s) < backend read timeouts (170 / 220 s) < frontend timeouts (200 / 250 s).

## Failure drills

| What you stop or break | What the user sees | Recover |
|---|---|---|
| `docker compose stop ai-service` | "Eliezer's AI is unavailable right now. Try again in a minute, or add the plant by name." The garden, watering and search still work. The API answers `503` in about 2 s | `docker compose up --wait` |
| `docker compose stop backend` | "Cannot reach the backend at …. Start it (docker compose up) and reload the page." | `docker compose up --wait`, then reload |
| upload a file that is not a photo | "Please fix: photo: The file is not a readable photo." | choose a JPEG, PNG or WebP |
| invalid interval via the API (e.g. 0 days) | "Please fix: watering_interval_days: …" | correct the field |
| reply lost after "I watered it" | "The backend did not answer in time. Your change may have been saved. Reload the page and check before trying again." | reload and check |

## Real-model run (optional)

Automated tests never call a real model. To use Gemma 4 E2B:

1. Install [Ollama](https://ollama.com/download) **0.20.6 or newer** (earlier 0.20.x releases had Gemma 4 tool-calling bugs), then `ollama pull gemma4:e2b` (4.6 GB download; about 5–6 GB of free RAM while it runs; no GPU needed, but expect tens of seconds per photo on a CPU).
2. Make it reachable from Docker without exposing it to your network (course local-inference guide, "Reach a host model server from Compose"): on Linux, bind Ollama to the Docker bridge only — `ip -4 addr show docker0` (usually `172.17.0.1`), then `OLLAMA_HOST=172.17.0.1:11434 ollama serve` (or set it with `sudo systemctl edit ollama`). On Docker Desktop, keep the default.
3. In `.env`: `AI_MODEL=ollama:gemma4:e2b` (and `OLLAMA_BASE_URL` only if you changed the default), then `docker compose up --build --wait`.
4. Send one photo first to warm the model up; the first answer after loading is the slowest.

Per-request caps (`ai-service/app/agents.py`): identify ≤3 model requests and 12,000 tokens; care ≤6 requests, 6 tool calls and 16,000 tokens.

### Evaluation results

Dataset: 10 cases in `ai-service/evals/cases.yaml` — 9 plant photos and 1 non-plant control case (photos from Wikimedia Commons, see `ai-service/evals/images/ATTRIBUTION.md`). Evaluators: IsInstance (schema), PlantDecision (control flow), Top1Species, InTop3, GenusMatch (score), HebrewNames.

| Date | Model / configuration | Cases | Assertions passed | GenusMatch (avg) | Notes |
|---|---|---|---|---|---|
| 2026-11-07 | fixed-answer baseline (`AI_MODEL=test`: always "rosemary") | 10 | 62.0% | 0.100 | deterministic stand-in, **not** model quality |
| — | `ollama:gemma4:e2b` | — | not run yet | — | run `AI_MODEL=ollama:gemma4:e2b OLLAMA_BASE_URL=http://localhost:11434/v1 uv run python -m evals.run_evals` and record the result here |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `port is already allocated` | 8000 or 8501 is in use | set `BACKEND_PORT` / `FRONTEND_PORT` in `.env` |
| identify always shows Rosemary / Lavender / Thyme and a "Demo mode" warning | `AI_MODEL=test` | expected; set a real model to identify real photos |
| identify returns "unavailable" with a real model | Ollama not running or not reachable from Docker; model not pulled | `ollama list`; check `OLLAMA_HOST` and `OLLAMA_BASE_URL`; `docker compose logs ai-service` shows the cause |
| every AI call returns 502 after a schema change | the contract drifted | regenerate `ai_openapi.json` and run the backend tests |

## Data sources

- **Plant names:** [Wikidata](https://www.wikidata.org/) (CC0) — plant species and genera that have a Hebrew Wikipedia article, with English and Hebrew labels. Rebuild with `cd backend && uv run python scripts/build_catalog.py` (needs network; output is committed as `backend/app/data/plants.csv`). No text is copied from Wikipedia.
- **Curated care** (`backend/app/data/care_curated.json`, 43 common garden and house plants): general guidance written with an AI assistant for this project; review it before relying on it.
- **AI-written care:** generated on first request, validated and stored; marked "Written by Eliezer's AI" in the app.
- **Evaluation photos:** Wikimedia Commons; each file keeps its own licence (`ai-service/evals/images/ATTRIBUTION.md`).

## Demo video

**TODO:** link to the English-narrated demo of `v1.0.0` (must play without signing in).

## AI-use note

Tools: Claude Code (Anthropic). · Help received: project scaffolding from the course's Recipe Box patterns, the plant-catalog script, curated care data, service code, tests and this README. · Checks I ran: **TODO — write what you personally ran and inspected** (for example the test commands above, the failure drills, and a real-model run).

## Open-source evidence

| Student (GitHub handle) | Official repository | License URL | Stars (date checked) | PR URL | Contribution summary | Merge evidence (main branch) |
|---|---|---|---|---|---|---|
| | | | | | | |
