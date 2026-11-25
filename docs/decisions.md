# Phase 0 decisions

Locked on 2026-11-17 from [architecture.md](./architecture.md) section 18 and [implementationplan.md](./implementationplan.md) Phase 0. These defaults stay in force unless a later phase records a change here.

## Deployed LLM

Updated 2026-11-18: **two hosted providers, split by node.**

| Nodes | Provider |
| --- | --- |
| `review` (stage-2 qualitative review) | **Groq** `openai/gpt-oss-20b` |
| All other LLM nodes (`parse_request`, `orchestrator_plan`, `orchestrator_revise`, `destination_research`, `logistics_prelim`, `logistics_sequence`, `budget` explanations, `budget_adjust`, `finalize`) | **Ollama Cloud** `nemotron-3-nano` |

A full live run needs `OLLAMA_API_KEY` and `GROQ_API_KEY`. If a key is missing, that provider stays off and the matching nodes keep their Phase 3 stubs.

The non-review model is `nemotron-3-nano` (`OLLAMA_MODEL`) at `https://ollama.com` (`OLLAMA_BASE_URL`). The client sends `Authorization: Bearer <OLLAMA_API_KEY>`. A localhost base URL does not need a key. `LLM_PROVIDER=groq` also sends those nodes to Groq.

Review always uses Groq. The model id is `openai/gpt-oss-20b` (`GROQ_MODEL`).

No personal data goes to either provider.

## OpenRouteService

No key is registered in Phase 0. `ORS_API_KEY` is optional. With it empty, or with `USE_LIVE_APIS=false`, routing stays on the curated offline graph. Register a free Standard-plan key before Phase 5 if live durations are needed. The Standard plan does not require a payment card.

## Product defaults (architecture section 18)

| Question | Locked default |
| --- | --- |
| Budget meaning | Total for the group, not per person. The parser records this as an assumption. |
| Accommodation | Inside the budget, including when the user only says flights are excluded. |
| Map view | Optional and post-MVP. The timeline, itinerary, and budget views are enough. |
| Durable resume | Off unless `CHECKPOINT_STORE_URL` is set. MVP clarification resume is in-memory for the browser session only. |
| Runtime cache | Off unless `CACHE_STORE_URL` is set. Static seed data is read-only. No cache, checkpoint, or export is written to the local filesystem at runtime on Vercel. |

No Marketplace store (Upstash, Turso, Neon, or otherwise) is selected. That choice waits until durable resume or a shared cache is actually required.

## Deployment shape

**Vercel Services** in one project, two services:

- `web` — Next.js App Router at `apps/web`
- `planner-api` — Python FastAPI at `services/planner-api`

Public ingress sends `/api/planner/*` to the planner API and every other path to the web app. Services is in beta on all Vercel plans. If the beta blocks a preview, the fallback is one Vercel project whose Next.js app calls a single Python function, with the same `/api/planner/*` prefix.

The canonical Python dependencies live in the root `pyproject.toml`. The package stays importable from the repo root through the early phases and moves under `services/planner-api` before deployment if that is what the service root needs. `services/planner-api/requirements.txt` lists only what the Phase 0 health app imports, so a later deploy of this stub does not pull the LangGraph stack early.

Python requirement is 3.12 or newer. The project virtualenv is CPython 3.12 (`.python-version`). The machine's default `python` is 3.15, which cannot install `langgraph` here because `zstandard` has no 3.15 wheel, so local commands use `.venv`.

## Catalog constraints (locked after Phase 1)

Later phases consume `data/seed/` as-is. Do not re-curate inside Phase 2–7. Gaps are planner constraints, not open research:

- Counts: 81 places, 80 restaurants, 32 hotels, 64 stations, 65 edges, 20 fares, 10 price bands, 12 climate months, 14 holidays (2026–2027).
- Almost all place, restaurant, hotel, and edge facts are `estimated`. Silver Nol 1/2/3+ fares are `verified`.
- Restaurant `cuisine` is `unspecified`. Match on area, `price_band`, and `meal_types`.
- Hotel `stars` is empty. Nightly ranges are estimated per hotel, not one shared number per tier and not hotel-site quotes. Use `Hotel.stay_option("peak" | "summer")`.
- `TransitStation.zone` is empty. Fare zone span is a planner-side area map.
- There is no RTA GTFS feed in the seed. Offline routing is the Metro/tram/walk graph, then straight line.
- `ORS_API_KEY` is still unset. Live routing waits for Phase 5.
- Museum of the Future is `reopening`. Business Bay, Al Quoz, and Dubai Creek are thin and merge with a Metro neighbour.
- Holiday effects are city-wide category rules (`drop_lunch`, `heritage_may_close_first_day`, `high_crowd`).

Details: [implementationplan.md](./implementationplan.md) section 1.7 and [research.md](./research.md) section 1.2.

## Itinerary auditor

Added 2026-11-22. A visitor can paste a Dubai itinerary, including one written by a general chatbot, at `/audit`.

The check is deterministic. It does not call an LLM and it does not start a LangGraph run.

- Names are matched to `data/seed/`. A name that does not match is reported and left out of the rebuild.
- The pasted order is scheduled with the offline Metro and tram graph, then priced with `compute_budget` and checked with `run_rules`.
- The rebuild keeps open catalog places from that paste, groups them with `sequence_itinerary`, adds meals, and swaps to a cheaper stay when the named hotel blows the budget.
- It does not invent a fresh trip from the rest of the catalog when nothing in the paste is usable.
- The public copy talks about places, hours, travel time, and dirhams. It does not ask the visitor to understand agents.

`POST /api/planner/audits` returns the verdict. `GET /api/planner/audits/example` returns the sample that should fail: Museum of the Future, two invented places, Eid al-Fitr, avoid crowds, Atlantis The Palm, and AED 900.

## Spoken trip description

Added 2026-11-25. The plan wizard accepts a spoken description in addition to typing.

- Provider: Sarvam speech-to-text, model `saaras:v4`, mode `transcribe`, `language_code=unknown`.
- Endpoint: `POST https://api.sarvam.ai/speech-to-text`, called only from `POST /api/speech` on the Next.js web service.
- Length: 30 seconds. That is the synchronous API limit. The browser enforces it. Batch and streaming Sarvam APIs are not used.
- The transcript is appended to the existing description box. **Fill in my details** is unchanged and still requires a click.
- `SARVAM_API_KEY` is optional. Empty means voice is off. The planner API does not read this variable.
- Audio is not stored and is not sent to LangGraph. The key is not sent to the browser.

## What is intentionally not decided

- Which external store, if any, holds cache and checkpoints.
- Whether the planner API needs a container image. Start as a standard Python service and switch only if the dependency size forces it.
