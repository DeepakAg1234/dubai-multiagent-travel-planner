# Dubai AI Travel Planner

A multi-agent trip planner for Dubai. LangGraph runs the agents. Python calculates prices, fares, hours, and review checks against the curated catalog in `data/seed/`. A missing model key keeps the deterministic stubs, so a fresh clone plans offline.

## Success criteria

| # | Criterion | Where it shows up |
| --- | --- | --- |
| 1 | A natural-language request becomes a structured Dubai itinerary | `python scripts/run_eval.py` and the example preset |
| 2 | Agents do different jobs | Timeline events from parse, research, logistics, budget, review, and finalize |
| 3 | Schedules and budgets come from the catalog, with provenance on every cost line | Review rules and the budget tab |
| 4 | At least one violation is detected and revised | Tight budget, Future Museum, Eid, or National Day presets |
| 5 | The active node and state changes are visible | Next.js timeline, graph view, and state inspector |
| 6 | A pasted itinerary can be checked without a model | `/audit` |
| 7 | A spoken description of up to 30 seconds becomes editable text | Plan wizard **Speak** control. Typing still works with no `SARVAM_API_KEY` |

Agreed eval thresholds: budget compliance or an explicit hotel-floor flag, feasible schedule, holiday rules held, provenance on every cost line, no closed or reopening place, no duplicate activity.

## Setup

Python 3.12 and Node 22. The repo virtualenv is `.venv` (the machine default may be a newer Python that cannot install LangGraph).

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
copy .env.example .env
.venv\Scripts\python scripts\build_db.py
npm install
npm run lint
```

`data/dubai.sqlite` is generated. Seed JSON is the source of truth. Rebuild after any seed edit:

```powershell
.venv\Scripts\python scripts\build_db.py
```

## Environment

Local values live in `.env` (gitignored). On Vercel, set the same names for Production and Preview. Leave a key empty to disable that provider. The stubs stay in place. Next.js does not automatically read this root file. `POST /api/speech` reads `SARVAM_API_KEY` from the environment, then from that root file if the environment does not already have it. The key stays on the server.

| Name | Role |
| --- | --- |
| `LLM_PROVIDER` | `anthropic`. Every node, including review, uses Claude |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Claude Opus 5.5 (`claude-opus-5-5`) |
| `ORS_API_KEY` | Optional OpenRouteService key |
| `USE_LIVE_APIS` | `false` keeps routing and weather on the seed |
| `MAX_REVISIONS`, `BUFFER_PCT`, `API_CALL_BUDGET` | Loop cap, buffer, and live-call budget |
| `CACHE_STORE_URL`, `CHECKPOINT_STORE_URL` | Leave empty on Vercel. Runtime cache and durable resume stay off |
| `LANGSMITH_TRACING` | Optional. Leave unset. Traces record request length, not the text |
| `SARVAM_API_KEY` | Optional. Speech-to-text for the plan wizard. Leave empty to keep **Speak** off. The Next.js route `/api/speech` reads it. The planner API does not |

Ollama and Groq are not used.

## Local development

Two processes. The web app proxies `/api/planner/*` to the API.

```powershell
.venv\Scripts\python -m uvicorn services.planner-api.api.main:app --reload --port 8000
npm run dev
```

Open the Next.js URL. The API health check is `GET /health` on port 8000, or `GET /api/planner/health` through the web app. Health reports whether keys are configured. It does not return key values.

Offline mode is the default: `USE_LIVE_APIS=false` and an empty `ANTHROPIC_API_KEY`. Holiday effects and the Metro/tram graph still apply. `python scripts/run_eval.py` forces that offline path even if your shell has a key.

## Demo

In the input panel:

1. **Example** — 4 days, AED 5000, culture, food, beaches, affordable hotel, avoid crowds.
2. **Tight budget** — `force:budget`. A luxury stay is revised down.
3. **Future Museum** — `force:museum`. Museum of the Future is reopening and is removed.
4. **Eid al-Fitr** — `force:eid`. Starts 2026-03-19, so lunch and heritage venues drop.
5. **National Day** — `force:national`. Starts 2026-12-02 with avoid crowds.

A request with no trip length stops at the clarification prompt. Answer in the same browser session. Durable resume needs `CHECKPOINT_STORE_URL`.

**Plan a trip** (`/plan`) collects the same request in steps. The card **Or describe your trip in your own words** takes typed text or a recording of up to 30 seconds. **Speak** posts the clip to `POST /api/speech`, which calls Sarvam Saaras (`saaras:v4`, transcribe) and appends the transcript to the box. **Fill in my details** is unchanged. With `SARVAM_API_KEY` empty, that route returns 503 and typing still works. The audio is not stored.

**Check a plan** (`/audit`) is the public counterpart. Paste a Dubai itinerary from ChatGPT or Claude, or load the sample. The page says which names are not in the catalog, which rules the plan breaks, and what a rebuilt version changed. The check does not call a model. It uses the catalog, the fare graph, and the review rules. `POST /api/planner/audits` is the endpoint. The sample text is `GET /api/planner/audits/example`.

Exports are JSON and Markdown downloads. Nothing is written to the server disk.

## Evaluation

```powershell
.venv\Scripts\python scripts\run_eval.py
```

Ten requests vary days (1–7), budget, hotel tier, interests, crowd preference, and start date (including Ramadan, Eid, National Day, and July). Results land in `evals/latest.json` and `evals/runs/` (both gitignored). The process exits 1 when a threshold fails.

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check src tests scripts services
```

`mypy src` still reports existing issues in `rules/` and the graph nodes, so CI runs ruff and pytest rather than mypy. GitHub Actions is in `.github/workflows/ci.yml`.

## Vercel

`vercel.json` defines two services:

- `web` — Next.js at `apps/web`
- `planner-api` — FastAPI at `services/planner-api/api/main.py`

`/api/planner/*` rewrites to the API. The API build runs `python scripts/build_db.py` and bundles `data/dubai.sqlite` read-only. Function duration is 300 seconds. Do not set `CACHE_STORE_URL` or `CHECKPOINT_STORE_URL` unless an external store is configured.

A preview with empty model keys runs the stub agents. That is the fake-LLM demo: streaming events, a revision loop from one of the force presets, and a downloadable itinerary. Confirm with:

```powershell
.venv\Scripts\python scripts\check_deploy.py
```

Then open the preview, run **Example** and **Future Museum**, and confirm the timeline advances and the export downloads.

## Catalog notes

Station zones are empty, restaurant cuisine is unspecified, and hotel nightly rates are estimated per property. Details are in [docs/architecture.md](docs/architecture.md) section 19 and [docs/implementationplan.md](docs/implementationplan.md) section 1.7.
