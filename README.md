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
                                                   -> ollama (the real model; idle in demo mode)
```

Only the backend reads or writes the database. The frontend never calls the AI service or the database, and the AI service never opens the database: it returns candidates that the backend validates before anything is saved. PostgreSQL and Ollama are infrastructure, not application services.

**Why Streamlit:** one language (Python) across all three services and the course's tested patterns; the cost is less layout control, so right-to-left Hebrew, the card grid and tap-to-open cards are done with injected CSS (`frontend/style.py`), aimed at the `st-key-*` classes Streamlit gives keyed elements. Theme colours (green, orange, white) live in `frontend/.streamlit/config.toml`.

---

## Setup

Requirements: Docker with Compose 2.24 or newer (`docker compose version`; Docker Desktop on macOS, Windows or Linux works, on Intel/AMD or Apple Silicon); [uv](https://docs.astral.sh/uv/) for local runs and tests (Python 3.14). The real model needs about 6 GB of free RAM and 5 GB of disk; on a smaller machine use demo mode (`AI_MODEL=test`).

```bash
cp .env.example .env   # optional: the stack also starts without it (real model)
```

| Setting | Where | Default | Meaning |
|---|---|---|---|
| `POSTGRES_PASSWORD` | `.env` | `eliezer-dev` | password of the `db` service; set your own |
| `AI_MODEL` | `.env` | `ollama:gemma4:e2b` | the real model in the `ollama` container (see [Real model and demo mode](#real-model-and-demo-mode)); `test` = **demo mode** (fixed stand-in answers, no download, no key, no cost) |
| `OLLAMA_BASE_URL` | `.env` | `http://ollama:11434/v1` | where the ai-service finds Ollama; `http://host.docker.internal:11434/v1` for Ollama on the host |
| `OLLAMA_PORT` | `.env` | `11435` | loopback port of the Ollama container, for the evaluation |
| `OLLAMA_NUM_THREAD` | `.env` | `4` | CPU threads the model uses (see [Speed](#speed-on-a-laptop-cpu)) |
| `GARDEN_REGION` | `.env` | `Israel (Mediterranean climate)` | region used in the AI instructions |
| `BACKEND_PORT` / `FRONTEND_PORT` | `.env` | `8000` / `8501` | host ports, if the defaults are taken |
| `FRONTEND_BIND` | `.env` | `127.0.0.1` | `0.0.0.0` opens the app to phones on your network (see [Use it from your phone](#use-it-from-your-phone)) |
| `DATABASE_URL` | backend | Compose: Postgres; image/local default: `sqlite:///./data/app.db` | where data lives |
| `AI_SERVICE_URL` / `BACKEND_URL` | backend / frontend | Compose service names | how services find each other |

## Run

```bash
docker compose up --build --wait
```

- App: <http://localhost:8501> · API docs: <http://localhost:8000/docs> · health: <http://localhost:8000/health>
- The first start loads the plant catalog (~1,500 plants) and a 3-plant demo garden; the backend logs `seeded … catalog plants`.
- The first start also downloads the model (4.6 GB) in the background: `docker compose logs -f ollama`. The garden works at once; photo identification and AI care answer "AI unavailable" until the download is done. Later starts skip it.
- `docker compose down` stops everything and **keeps** your data (the `db-data` volume).
- `docker compose down -v` **deletes** your garden, the AI-written care and the downloaded model. The next start reloads the catalog and demo garden, and downloads the model again.
- Backup: `docker compose exec db pg_dump -U eliezer eliezer > backup.sql` · restore into a fresh stack: `docker compose exec -T db psql -U eliezer eliezer < backup.sql`

### Use it from your phone

1. In `.env`: `FRONTEND_BIND=0.0.0.0`, then `docker compose up -d`. Only the app (port 8501) opens to your network; the API, the AI service and the database stay closed.
2. Find this computer's address on the Wi-Fi: `hostname -I` on Linux (the first one, e.g. `10.100.102.187`), `ipconfig getifaddr en0` on macOS, `ipconfig` on Windows.
3. If a firewall is on, allow port 8501 from your network only. Ubuntu: `sudo ufw allow from 10.100.102.0/24 to any port 8501 proto tcp` (use your own network's first three numbers).
4. On the phone, on the same Wi-Fi: `http://<that address>:8501`.

There is no login: anyone on that Wi-Fi can open the app, so use it on a network you trust. Over plain `http://` phones do not allow the live camera, so the "Use my camera" switch is hidden there; the upload button offers the phone's camera instead.

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
| ai-service | `uv run pytest` | demo mode, identify validator (repairs a fixable answer, retries an unusable one), care validator (forces a retry), thinking off for Ollama models, 422/429/500/502/504 mapping, tools, no photo or text in logs, eval harness |
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
| backend `POST /plants/identify` | multipart `photo` (JPEG/PNG/WebP, ≤15 MB, ≤60 megapixels) | `200` candidates | `422` bad photo (no AI call) · `503` AI down, timed out, over budget or 5xx · `502` AI output broke the contract |
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

## Real model and demo mode

`docker compose up` uses **Gemma 4 E2B** in the `ollama` container by default; no `.env` needed. The first start downloads the model into the `ollama-models` volume (4.6 GB; `docker compose logs -f ollama`). Until it is done, photo identification and AI care answer "AI unavailable"; the garden works meanwhile. It needs about 5–6 GB of free RAM while the model runs and about 5 GB of disk. No GPU is needed: a photo takes about 15–25 seconds on a laptop CPU, plus about 20 seconds when the model has to load first (it stays loaded for 30 minutes after use).

**Demo mode** (`AI_MODEL=test` in `.env`): fixed stand-in answers (always rosemary, lavender, thyme), no download, no key, no cost; the `ollama` container stays idle. CI and `scripts/clean-checkout.sh` run in demo mode, and automated tests never call a real model.

The image (`ollama/Dockerfile`) is the official Ollama release, pinned to 0.40.15 and checked against its published SHA-256, without the GPU libraries: 234 MB instead of the official image's 3.4 GB download. On a machine with an NVIDIA GPU, replace `build: ./ollama` with `image: ollama/ollama:0.40.15` and add a GPU reservation (Docker docs, "GPU support in Compose").

**Ollama on the host instead:** install [Ollama](https://ollama.com/download) 0.20.6 or newer (earlier 0.20.x releases had Gemma 4 tool-calling bugs) and `ollama pull gemma4:e2b`. Make it reachable from Docker without exposing it to your network (course local-inference guide, "Reach a host model server from Compose"): on Linux, bind it to the Docker bridge only, usually `OLLAMA_HOST=172.17.0.1:11434` (set it with `sudo systemctl edit ollama`); on Docker Desktop, keep the default. Then set `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1` in `.env`.

### Speed on a laptop CPU

Measured on an Intel Core 7 150U laptop (12 threads, Docker Desktop), identifying one photo went from timing out after 150 s to about 15–25 s with three settings:

| Setting | Where | Why |
|---|---|---|
| 4 CPU threads (`OLLAMA_NUM_THREAD`) | `ollama/entrypoint.sh` stores it in the model | Ollama starts one thread per CPU; in Docker Desktop's VM on a busy laptop the threads keep waiting for each other. 12 threads wrote 0.3–0.7 tokens/s, 4 threads 7.6. On a machine with many free cores, try more. |
| thinking off | `model_settings()` in `ai-service/app/agents.py` | Through the OpenAI API, Gemma 4 thinks before it answers: ~800 hidden tokens per photo, two minutes on this CPU |
| repair before retry, compact JSON | `check_identification` and the identify instructions | a retry resends the photo and doubles the time, so one malformed guess among good ones is dropped and the order is fixed in code; indentation costs tokens |

Per-request caps (`ai-service/app/agents.py`): identify ≤3 model requests and 12,000 tokens; care ≤6 requests, 6 tool calls and 16,000 tokens.

### Evaluation results

Dataset: 10 cases in `ai-service/evals/cases.yaml` — 9 plant photos and 1 non-plant control case (photos from Wikimedia Commons, see `ai-service/evals/images/ATTRIBUTION.md`). Evaluators: IsInstance (schema), PlantDecision (control flow), Top1Species, InTop3, GenusMatch (score), HebrewNames.

| Date | Model / configuration | Cases | Assertions passed | GenusMatch (avg) | Notes |
|---|---|---|---|---|---|
| 2026-11-07 | fixed-answer baseline (`AI_MODEL=test`: always "rosemary") | 10 | 62.0% | 0.100 | deterministic stand-in, **not** model quality |
| 2026-11-08 | `ollama:gemma4:e2b` (Ollama 0.40.15 container, CPU only, 4 threads, thinking off) | 10 | 88.0% | 0.700 | one model request per photo, 16.7 s average on an Intel Core 7 150U laptop; wrong genus for rosemary (lavender), fig (avocado) and pothos. Rerun: with the stack running, `AI_MODEL=ollama:gemma4:e2b OLLAMA_BASE_URL=http://localhost:11435/v1 uv run python -m evals.run_evals` in `ai-service/` |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `port is already allocated` | 8000, 8501 or 11435 is in use | set `BACKEND_PORT` / `FRONTEND_PORT` / `OLLAMA_PORT` in `.env` |
| `env_file` or `depends_on` errors when Compose reads the file | Compose older than 2.24 | update Docker Desktop or the Compose plugin |
| the model fails to load on macOS or Windows | Docker Desktop gives its VM too little memory | Docker Desktop → Settings → Resources: give it at least 8 GB, or use demo mode |
| identify always shows Rosemary / Lavender / Thyme and a "Demo mode" warning | `AI_MODEL=test` | expected in demo mode; remove the line from `.env` for the real model |
| identify says "AI unavailable" right after the first start | the model is still downloading, or the download failed (no network, disk full) | `docker compose logs ollama`; after a failure, fix the cause and run `docker compose restart ollama` (the download resumes) |
| identify returns "unavailable" with a real model | Ollama not running or not reachable; the model ran out of memory | `docker compose ps` (is `ollama` healthy?); `docker compose logs ollama ai-service` shows the cause; close memory-hungry apps |
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
| itay-malka | [nilbuild/developer-roadmap](https://github.com/nilbuild/developer-roadmap) | [license](https://github.com/nilbuild/developer-roadmap/blob/master/license) | 371,489 (2026-11-08) | [#10523](https://github.com/nilbuild/developer-roadmap/pull/10523) | Pointed 5 resource links that opened Spanish pages to their English versions (cloud computing, C++, network engineer and Power BI roadmaps) | merged 2026-11-03 into `master`, merge commit [`1d52613`](https://github.com/nilbuild/developer-roadmap/commit/1d52613a622e91075d8c1dee3986afb0dfda792c) |
| itay-malka | [nilbuild/developer-roadmap](https://github.com/nilbuild/developer-roadmap) | [license](https://github.com/nilbuild/developer-roadmap/blob/master/license) | 371,489 (2026-11-08) | [#10524](https://github.com/nilbuild/developer-roadmap/pull/10524) | Renamed a resource title from "Queues - Coursera" to "Data Structures - Coursera" to match the linked course (computer science roadmap) | merged 2026-11-03 into `master`, merge commit [`8cf7dd4`](https://github.com/nilbuild/developer-roadmap/commit/8cf7dd429c78fdc79eed1723392f8331ebaa8e3e) |
