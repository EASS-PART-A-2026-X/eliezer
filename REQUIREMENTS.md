# eliezer: project requirements

The requirements for the EASS Class X course product (HIT, Semester A 2026–27), collected from the [course lecture notes](https://github.com/EASS-PART-A-2026-X/lecture-notes) (commit `c1a6a30`, read 7 Nov 2026).

**The course README is authoritative.** If this file and the course disagree, the course wins. Re-check the [course README](https://github.com/EASS-PART-A-2026-X/lecture-notes/blob/main/README.md) when the notes are updated.

How to read the tags:

- **Required**: part of an assignment hand-in in the course README, so it is graded.
- **Checkpoint**: a "must work" row from a lecture's completion check. Later lectures build on it.
- **Recommended**: course advice that is not graded on its own.

---

## 0. Product decisions to fill in

The course asks for a one-page product sketch (Lecture 1). Fill these in before writing code; the record fields drive every later layer.

| Decision | Value |
|---|---|
| Domain (one narrow area, e.g. "save and adapt recipes", not "a food platform") | **Eliezer — your garden master:** manage the plants in your own garden and when to water them |
| Purpose: the need, and the bad situation it prevents | Plants die because nobody remembers when each was last watered or what it needs; care advice is scattered and often only in English |
| Operational principle: "after *someone* does *A*, then *B*; afterwards *C* holds" | After I photograph a plant and confirm what Eliezer identified, it appears in my garden with a watering countdown and care steps; after I press "I watered it", the countdown starts again, and it is still there tomorrow |
| Three user stories: "As a *user*, I can *action* so that *benefit*" | Identify a plant from a photo; add a plant by Hebrew/English/Latin name; see days left until watering and mark it watered (plus: switch the UI to Hebrew) — see README |
| Main record: 4–6 fields, each with a type and a limit | `GardenPlant`: `plant_id` (catalog FK), `nickname` (≤100), `location` (≤100), `watering_interval_days` (1–60), `last_watered_at` (UTC); catalog `Plant` with EN/HE names and care |
| AI service job: one job with structured output (e.g. messy text in, record out) | Photo → up to 3 candidate species (EN/HE names, confidence); plant names → care guide (interval, sunlight, EN + HE steps). Gemma 4 E2B via Ollama; demo stand-in when `AI_MODEL=test` |
| Individual or pair (each student still explains their own work) | **TODO** |
| Frontend framework (Streamlit is the course default; React is allowed) | Streamlit, with an English/Hebrew toggle and right-to-left CSS |
| Database | PostgreSQL 18 as the `db` Compose service (infrastructure); the backend image defaults to SQLite for the standalone EX1 check |

The operational principle is replayed by the Lecture 5 end-to-end test and in the final demo, so choose one you can demonstrate.

---

## 1. Deadlines

All deadlines are **23:59 Israel time**. Submit through the instructor's submission channel as `https://github.com/EASS-PART-A-2026-X/eliezer`. Use the same repository for all three assignments.

| Date | What is due |
|---|---|
| Mon 2 Nov 2026 | Checkpoint: first upstream open-source PR opened |
| **Mon 9 Nov 2026** | **EX1: Backend** |
| Mon 23 Nov 2026 | Checkpoint: second upstream PR opened |
| **Mon 30 Nov 2026** | **EX2: Frontend plus backend** |
| Mon 7 Dec 2026 | Checkpoint: third upstream PR opened |
| Mon 21 Dec 2026 | Checkpoint: release candidate `v1.0.0-rc.1` with green CI |
| Mon 4 Jan 2027 | Demo rehearsal (Meeting 12) |
| **Mon 11 Jan 2027** | **EX3: Complete product, live demo, English-narrated video, and three merged open-source PRs** |

Graders must be able to open and clone the repository with their own accounts. Confirm grader access with the instructor.

---

## 2. Architecture (Required)

```text
browser
  -> frontend    (Streamlit or React)      :8501
  -> backend     (FastAPI + Pydantic)      :8000  -> SQLite (only the backend)
  -> ai-service  (FastAPI + Pydantic AI)   :8001  (called only by the backend)
```

| ID | Requirement |
|---|---|
| ARCH-1 | Three **application** services: frontend, backend and AI service. A database, Redis, proxy or monitoring container is infrastructure and does not count as one of the three. |
| ARCH-2 | Data flows user → frontend → backend → AI service. **Only the backend touches persistent storage.** |
| ARCH-3 | The frontend never reads or writes the database and never calls the AI service directly. |
| ARCH-4 | The AI service is an independent service with its own HTTP contract. The backend calls it over HTTP with validated input and output. An agent class inside the backend does **not** count. |
| ARCH-5 | The AI service returns a *candidate* result. The backend validates it before anything is saved. |
| ARCH-6 | Docker Compose is the required way to run all three services. Add infrastructure only when you can justify it. |
| ARCH-7 | SQLite is enough; PostgreSQL is allowed. Data must survive the documented restart procedure. |
| ARCH-8 | Apply input validation, secret management, appropriate permissions and access controls where the domain needs them. |

### Recommended repository layout

```text
eliezer/
├── backend/        FastAPI app, pyproject.toml, uv.lock, tests/, Dockerfile
├── frontend/       Streamlit app, pyproject.toml, uv.lock, tests/, e2e/, Dockerfile
├── ai-service/     FastAPI + Pydantic AI, pyproject.toml, uv.lock, tests/, evals/, Dockerfile
├── scripts/clean-checkout.sh
├── .github/workflows/ci.yml
├── compose.yaml
├── .env.example    (committed)
├── .env            (git-ignored, never committed)
└── README.md
```

### Course reference stack (pinned October 2026)

These are recommended versions, not requirements. Your own `uv.lock` records what you actually use.

- **Python** 3.14 · **uv** for dependencies · **pytest** 9.1.1 · **ruff** for lint and format
- **Backend:** `fastapi[standard]==0.143.3`, `sqlmodel==0.0.48`, `tenacity==9.1.4` (retries), plus an HTTP client for calling the AI service
- **AI service:** `fastapi[standard]==0.143.3`, `pydantic-ai-slim[openai]==2.57.0`
- **Frontend:** `streamlit==1.66.0`, `httpx==0.28.1`; dev dependencies `respx`, `pytest-playwright`

---

## 3. Backend: EX1, extended in EX3

### EX1 hand-in (Required)

The EX1 hand-in is a CRUD API with Pydantic validation, persistent data, tests, a backend Dockerfile, and setup, run and test instructions.

| ID | Requirement | Tag |
|---|---|---|
| BE-1 | Five CRUD routes for the main record, plus `GET /health` returning `{"status":"ok"}`. | Required |
| BE-2 | Correct status codes: create returns **201** with the resource; delete returns **204** with no body; a missing id returns **404** (DELETE included); invalid input returns **422**. | Checkpoint |
| BE-3 | Separate Pydantic models for **Create**, **Update** and **Public**. Clients cannot set `id`; PATCH applies only the fields sent; responses always include `id`. | Checkpoint |
| BE-4 | Every model uses `extra="forbid"` and puts a limit on every field. List query parameters are bounded, e.g. `limit: Query(ge=1, le=100)`. | Checkpoint |
| BE-5 | Persistence with SQLModel and SQLite. `DATABASE_URL` is configurable and documented. The database file lives in `/app/data` on a named volume (`backend-data`). | Required |
| BE-6 | The app's lifespan creates the tables and runs an **idempotent, validated seed**, then disposes of the engine on shutdown. | Checkpoint |
| BE-7 | `git status` never shows a `.db` file or a `data/` folder; both are git-ignored. | Checkpoint |
| BE-8 | Tests: `uv run pytest` passes with **at least 8 tests**. Tests assert status codes **and** response bodies, use a fresh store per test, and include seed tests and a **restart test** showing data survives. Lecture 2's CRUD tests stay unchanged when persistence is added. | Required |
| BE-9 | `uv run ruff check .` and `uv run ruff format --check .` are clean. | Checkpoint |
| BE-10 | The Dockerfile builds an image that runs as a **non-root user** (`docker exec backend id` shows `uid=10001(appuser)`). A record survives `docker rm -f backend` followed by a new `docker run` with the same volume. | Required |
| BE-11 | The README has the setup, run and test commands for both local and Docker use, and documents `DATABASE_URL`. | Required |

EX1 self-check, from `backend/` (Lectures 2 and 3):

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
docker build -t eliezer-backend .
docker run -d --name backend -p 127.0.0.1:8000:8000 -v backend-data:/app/data eliezer-backend
curl -sS --retry 10 --retry-all-errors --retry-delay 1 localhost:8000/health
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/<records>/999              # 404
curl -s -o /dev/null -w "%{http_code}\n" --json '{}' http://localhost:8000/<records>      # 422
docker exec backend id                                                                   # uid=10001
```

### Calling the AI service: EX3 (Lectures 7 and 9)

| ID | Requirement | Tag |
|---|---|---|
| BE-12 | An endpoint that sends user input to the AI service, validates the result and saves it (Recipe Box uses `POST /recipes/from-text`). It returns the new record with its `id`. | Required |
| BE-13 | Error mapping: AI service refused, timed out or returned 5xx → **503** `{"detail":"AI service unavailable"}`; AI service returned 4xx or a broken body → **502**; invalid user input → **422** with **zero** calls to the AI service. | Checkpoint |
| BE-14 | Fail fast. With the AI service stopped, the request returns 503 within a few seconds, not after 30 or more. | Checkpoint |
| BE-15 | Retries happen in **one layer only**. Timeouts, connect errors, 503 and 504 get at most 3 attempts with backoff. 429, 502, 500, other 4xx and a broken 200 get exactly one try. Tests prove each case. | Checkpoint |
| BE-16 | A contract test (`test_contract.py`) checks the backend against a freshly generated `ai_openapi.json` snapshot. The README shows the command that regenerates the snapshot. | Checkpoint |
| BE-17 | `uv run pytest` in `backend/` passes with no network (Wi-Fi off). | Checkpoint |

---

## 4. Frontend: EX2, extended in EX3

### EX2 hand-in (Required)

The EX2 hand-in is a browser UI integrated with EX1: core flows, error states, one automated UI or integration flow, and reproducible run instructions.

| ID | Requirement | Tag |
|---|---|---|
| FE-1 | A browser-based UI at `:8501`. A CLI alone is not enough. | Required |
| FE-2 | The UI talks only to the backend API, through **one module that owns all HTTP calls**. `grep -nE "sqlmodel\|sqlite\|st\.connection" *.py` prints nothing, and the main app file does not import `httpx` directly. | Checkpoint |
| FE-3 | Core flows: the list shows the seed rows; creating a record shows a success message and the new record at once; an edit persists after a page reload; a delete also removes the record from the backend. | Required |
| FE-4 | Four states on every screen: **loading**, **empty** (the empty state tells the user what to do first), **error** and **success**. | Required |
| FE-5 | With the backend stopped, the page shows a next step and no traceback. After a backend restart and a page reload, it recovers. | Checkpoint |
| FE-6 | If the reply is lost after a write, the UI says the change **may have been saved**. | Checkpoint |
| FE-7 | A 422 is shown as a readable sentence that names the field, never as raw JSON or a traceback. | Checkpoint |
| FE-8 | Tests: AppTest unit tests plus an HTTP-boundary test (`uv run pytest`), and **one Playwright browser flow** (`uv run pytest e2e --base-url http://localhost:8501`) that replays the operational principle. Each test fails when the thing it protects is broken. | Required |
| FE-9 | `ruff check` and `ruff format --check` are clean. | Checkpoint |
| FE-10 | The README has a "Test the frontend" section with the exact commands, plus a manual-checks list containing the error sentences. | Required |

### The AI flow: EX3

| ID | Requirement | Tag |
|---|---|---|
| FE-11 | Submitting input for the AI shows a spinner, then the new saved record appears in the list. | Checkpoint |
| FE-12 | With the AI service stopped, the UI shows a friendly message at once, and the ordinary CRUD screens still work. | Checkpoint |
| FE-13 | Frontend tests cover the AI flow. | Checkpoint |

---

## 5. AI service: EX3 (Lectures 6 and 9)

| ID | Requirement | Tag |
|---|---|---|
| AI-1 | A separate FastAPI service using Pydantic AI on port `8001`. It is **not** published to the host in Compose, so `curl localhost:8001/health` fails from the host. | Required |
| AI-2 | The agent has an `output_type` (a Pydantic model), `instructions`, a **tool backed by deps**, a **plain tool**, and an **output validator**. | Checkpoint |
| AI-3 | Endpoints: a job endpoint (Recipe Box uses `POST /extract`) that returns schema-valid JSON, and `GET /health` returning `{"status":"ok"}`. | Checkpoint |
| AI-4 | The service never opens the database. | Required |
| AI-5 | Tests use deterministic substitutes (`TestModel` or `FunctionModel`), with `ALLOW_MODEL_REQUESTS = False` in `tests/conftest.py`. `uv run pytest` passes with **no API key and no network**. | Required |
| AI-6 | Removing the output validator's `raise` makes at least one test fail. | Checkpoint |
| AI-7 | Agent failures map to **429, 502, 504 and 500**, each with a test. Usage is logged **without the user's text**. | Checkpoint |
| AI-8 | The model is chosen by configuration (e.g. `AI_MODEL=test` for the deterministic model). Instructions for running a real model are **separate and optional**; a free local model such as Ollama is fine. | Required |
| AI-9 | The code uses no outdated Pydantic AI API names. Assistants often suggest old ones, so check suggestions against the current docs. | Checkpoint |

### Evaluation dataset (Required)

| ID | Requirement |
|---|---|
| EV-1 | `uv run python -m evals.run_evals` in `ai-service/` prints a results table with an **Averages** row. |
| EV-2 | 8–10 cases and **3 or more evaluators**. Separate schema checks, domain-quality checks and control-flow checks. |
| EV-3 | A **dated** results row in the README that names the model and configuration used. If the run used canned outputs or a fake model, label it as such. Record unavailable measurements as unknown. |

---

## 6. Compose, configuration and failure behavior: EX3 (Lectures 8 and 9)

| ID | Requirement | Tag |
|---|---|---|
| CMP-1 | `compose.yaml` runs all three services, each with a healthcheck. `docker compose up --build --wait` ends with three `Healthy` lines. | Required |
| CMP-2 | A **clean clone with no `.env`** starts the whole stack. | Checkpoint |
| CMP-3 | Data survives `docker compose down` followed by `up`. `down -v` resets to the seed data, and the README warns about this. | Required |
| CMP-4 | `.env` is git-ignored (`git check-ignore -v .env` prints a rule; `git ls-files .env` prints nothing). `.env.example` is committed and lists **every** setting without real values. | Required |
| CMP-5 | The backend reaches the AI service by its Compose service name. Ports can be overridden with `BACKEND_PORT` and `FRONTEND_PORT`. | Recommended |
| CMP-6 | Failure drills, each recorded in the README's failure table: stop `ai-service` → the backend returns 503 within seconds, the UI shows a friendly message and CRUD still works; stop the backend → the UI shows a friendly message; send invalid input → a readable error. | Required |

Clean-clone self-check (Lecture 8):

```bash
git clone https://github.com/EASS-PART-A-2026-X/eliezer.git ~/clean-check
cd ~/clean-check
docker compose -p clean-check up --build --wait
curl -s localhost:8000/health
docker compose -p clean-check down -v
```

---

## 7. CI and release: EX3 (Lecture 10)

| ID | Requirement | Tag |
|---|---|---|
| CI-1 | `.github/workflows/ci.yml` runs each service's tests and a Compose smoke test, and is **green on the exact commit you tag**. | Required |
| CI-2 | `scripts/clean-checkout.sh` copies `.env.example`, starts the stack from a clean checkout, and prints `Clean checkout OK: <sha>`. | Checkpoint |
| CI-3 | Tag `v1.0.0-rc.1` on a green commit (Lecture 10), then `v1.0.0` on the final green commit you demo and submit. | Required |
| CI-4 | Automated tests make no paid API calls. | Required |

Check CI for a commit:

```bash
gh run list --workflow ci.yml --commit "$(git rev-parse HEAD)" --json status,conclusion,headSha
```

The result must show `"status": "completed"` and `"conclusion": "success"`.

Recommended hardening (not graded on its own):

- [ ] Actions pinned by full SHA; `permissions: contents: read`; `persist-credentials: false`
- [ ] `actionlint` and `zizmor` report no problems
- [ ] `uv audit` output read, with a README row for each ignored ID
- [ ] Containers run as non-root, with `cap_drop: [ALL]` and `no-new-privileges`; `ai-service` not published
- [ ] `v1.0.0-rc.1` published as a GitHub pre-release

---

## 8. README contents

The README grows with each assignment. By EX3 it must contain:

- [ ] **Product sketch** (Lecture 1): name, one-sentence pitch, purpose, operational principle, user stories, data sketch, what the AI service does, data flow
- [ ] **Setup**: requirements and configuration (`.env.example`, `DATABASE_URL`, `AI_MODEL`, …)
- [ ] **Run**: `docker compose up --build` and the URLs; `down` keeps data, `down -v` deletes it; data lives in the `backend-data` volume at `/app/data`; optional backup with `docker compose cp backend:/app/data/app.db backup.db`
- [ ] **Test**: the exact command for each service, plus `scripts/clean-checkout.sh`
- [ ] **Manual checks**: the error sentences users see
- [ ] **AI contract**: contract table, data flow, and the command that regenerates the `ai_openapi.json` snapshot
- [ ] **Failure drills**: what to stop, and what the user sees
- [ ] **Real-model run** (optional): variables, cost limits, and the **dated** evaluation results table naming model and configuration
- [ ] **Troubleshooting**: symptom, cause and fix for problems you actually hit
- [ ] **AI-use note**: tools used, help received, checks performed (no prompt logs needed)
- [ ] **Open-source evidence table** (see section 10)
- [ ] **Demo video link** next to the final revision (`v1.0.0`)

---

## 9. EX3 demo (Required)

### Recorded video

- One screen recording of the **actual running application** with **spoken English narration** by you (in a pair, both partners narrate a meaningful part). Aim for about 5 minutes; 4–7 minutes is the target range.
- It must cover:
  1. **Purpose and architecture**: the problem, and the real frontend → FastAPI backend → separate Pydantic AI service path, with the backend as the only owner of persistent data.
  2. **Working product**: a meaningful browser workflow, showing that saved state reaches the backend and persists.
  3. **AI functionality**: a request to the separate service and a validated result. Say whether the recording uses a real model or a deterministic test model.
  4. **Failure and recovery**: one deliberate fault, the user-visible response, then restoring normal behavior.
  5. **Verification**: the final tag or commit, green CI for it, one dated evaluation result, and one known limitation.
- Link the video from the README **and** the EX3 submission. It must play without login or an access request; test the link while signed out.
- Don't commit large media files, show tokens, or record real people's data. Use synthetic data.
- Slides, mock-ups, generated voice-overs and synthetic animations are not accepted in place of the running app.

### Live demo (Meeting 13)

- Run `v1.0.0`, tagged on a green-CI commit, from a clean clone of that tag (`git clone --branch v1.0.0 <repo-url> demo`).
- Have the README open at the runbook and the evidence table.
- Follow the rehearsal checklist: clean checkout → happy path (list, add, edit, delete, AI flow) → one failure drill → tests → evals → evidence table.
- Individual technical discussion: each student explains their own work and PRs without an assistant.

---

## 10. Open-source contributions (Required, per student)

| ID | Requirement |
|---|---|
| OSS-1 | **Three distinct PRs of your own, merged** into established open-source projects. Credit is per student; each PR counts for one student only. Any size counts (docs, typos, tests, fixes, features). |
| OSS-2 | Qualifying repository: the official public upstream repository on GitHub, open-source licensed, actively maintained, with **more than 10,000 stars** on the day you open the PR. Not a fork, a classroom repository or a personal copy. |
| OSS-3 | "Merged" means the change reached the main development branch (`main`, `master`, or a documented equivalent). Open, approved-but-unmerged and closed PRs don't count. |
| OSS-4 | Read each project's CONTRIBUTING guide and AI-use policy first. **Write all maintainer-facing text yourself** (PR descriptions, issue comments, review replies). Don't split one change into artificial PRs. |

README evidence table, one row per PR:

| Student (GitHub handle) | Official repository | License URL | Stars (date checked) | PR URL | Contribution summary | Merge evidence (on the main branch) |
|---|---|---|---|---|---|---|

Check a PR's evidence:

```bash
gh repo view OWNER/REPO --json stargazerCount,licenseInfo,isFork,defaultBranchRef
gh pr view PR_URL --json state,mergedAt,baseRefName,mergeCommit
```

---

## 11. AI-assisted development rules

- AI coding assistants are allowed from week 1. You must **understand and verify everything you submit** and be able to explain it individually.
- Keep a short AI-use note in the README: tools, help received, checks performed.
- Secrets and private user data never reach Git.
- Not OK: submitting work you can't explain; letting an assistant write maintainer-facing open-source text.

---

## 12. Out of scope

Not required, and not needed for full credit:

- Redis, Kubernetes, cloud hosting, JWT, multiple database engines
- Paid accounts, AWS Educate, a GPU, or a paid model API
- Executing generated code in the AI service
- The FactoryOps / Metamachine extension (optional; adds no grade weight and replaces nothing)

---

## 13. Final check before submitting

This is the course's grader-style self-check; a grader follows the same path.

- [ ] `.env.example` lists every setting without real values; `git check-ignore -v .env` names the ignore rule
- [ ] `docker compose up --build` starts all three services, and `docker compose ps` shows them healthy
- [ ] Core flows work in the browser, with loading, empty and error states
- [ ] The README's test commands pass with no key and no model calls
- [ ] CI is `completed` / `success` for the commit being submitted
- [ ] Failures read clearly: AI service down, backend down, invalid input
- [ ] Data survives `down` then `up`, and the README warns that `down -v` wipes it
- [ ] Real-model instructions are separate and optional
- [ ] The evaluation results table is dated and names the model and configuration
- [ ] The README has the runbook sections and the AI-use note
- [ ] The video link plays while signed out
- [ ] Three merged upstream PRs per student are in the evidence table
- [ ] `git status` is clean afterwards
