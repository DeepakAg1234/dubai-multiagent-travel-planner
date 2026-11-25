# Deployment plan — Dubai AI Travel Planner

Companion to [architecture.md](./architecture.md), [decisions.md](./decisions.md), and [implementationplan.md](./implementationplan.md). The committed shape is already in the root `vercel.json`.

## Short answer

Yes. The MVP ships as **one Vercel project**. You do not stand up a second host, a database, or a cache.

That one project contains two services that build separately and deploy together:

| Service | What it is | Root |
| --- | --- | --- |
| `web` | Next.js App Router UI | `apps/web` |
| `planner-api` | Python FastAPI + LangGraph, Server-Sent Events | repo root, entry `services/planner-api/api/main.py:app` |

Public traffic hits one URL. `/api/planner/*` is rewritten to `planner-api`. Every other path goes to `web`. The browser never talks to Python or LangGraph directly.

Accounts you still need, but do not deploy:

- **Ollama Cloud** (`https://ollama.com`, `nemotron-3-nano`) for every LLM node except review.
- **Groq** (`openai/gpt-oss-20b`) for the review node.
- **OpenRouteService** only if you turn live routing on.

Empty model keys are a valid preview. The stub agents still stream a plan. Leave `USE_LIVE_APIS=false` so weather and routing stay on the seed.

Vercel Services is in beta on all plans. If a preview cannot start the Python service, the fallback is the same project with one Next.js app calling a single Python function under the same `/api/planner/*` prefix. Do not split the UI and the API onto two hosts for the MVP.

## What you do not deploy

| Piece | MVP treatment |
| --- | --- |
| Database | None. `python scripts/build_db.py` runs in the planner-api build and bundles `data/dubai.sqlite` read-only. Seed JSON in git is the source of truth. `data/*.sqlite` stays gitignored. |
| Cache and checkpoints | Off. Leave `CACHE_STORE_URL` and `CHECKPOINT_STORE_URL` empty. Clarification resume lives in the browser session for that request only. |
| Exports | Generated in the response. Nothing is written to the function filesystem. |
| Local Ollama | Do not set `OLLAMA_BASE_URL` to localhost. The deployed app calls Ollama Cloud. |
| Streamlit | Local experiments only. Not in `vercel.json`. |
| Map tiles, Blob, Redis, Postgres | Post-MVP. No Marketplace store is selected. |

Functions are stateless and can scale to zero. Do not write cache, checkpoints, exports, or a generated database at runtime.

## Constraints that shape the deploy

- Python **3.12** (`.python-version`). The planner function `maxDuration` is **300 seconds**, which matches the platform default. A full graph with live models must finish inside that window. Streaming is how the UI stays alive during the run.
- Request and response bodies are limited to **4.5 MB**. SSE event chunks and on-demand JSON/Markdown exports fit. Do not upload the catalog through the request body.
- The Python install is the root `pyproject.toml` (`services/planner-api/requirements.txt` is `-e ../..`). Watch the function bundle. Trim dependencies before moving the planner to a container image.
- Node **22** for the web service. Stay on the default Node.js runtime. Do not set `runtime = "edge"`.
- `web` receives `PLANNER_API_INTERNAL_URL` from a service binding. Public calls still use the rewrite, so the browser stays on the same origin. The API CORS allow-list is localhost only and is for local uvicorn, not for the public site.

## Environments

Set the same names as `.env.example` on **Preview** and **Production**. The dashboard is the source of truth. Do not commit `.env`.

| Name | Preview (stub demo) | Production (real models) |
| --- | --- | --- |
| `LLM_PROVIDER` | `ollama` | `ollama` |
| `OLLAMA_API_KEY` | empty | set |
| `OLLAMA_BASE_URL` | `https://ollama.com` | `https://ollama.com` |
| `OLLAMA_MODEL` | `nemotron-3-nano` | `nemotron-3-nano` |
| `GROQ_API_KEY` | empty | set |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | `openai/gpt-oss-20b` |
| `ORS_API_KEY` | empty | empty unless live routing is on |
| `USE_LIVE_APIS` | `false` | `false` until OpenRouteService, Overpass, and Open-Meteo are intentionally enabled |
| `MAX_REVISIONS` | `3` | `3` |
| `BUFFER_PCT` | `10` | `10` |
| `API_CALL_BUDGET` | `40` | `40` |
| `CACHE_STORE_URL` | empty | empty |
| `CHECKPOINT_STORE_URL` | empty | empty |
| `LANGSMITH_TRACING` | unset | unset |
| `SARVAM_API_KEY` | empty, unless the preview should speak | set, on the web service only |

`LLM_PROVIDER=groq` also sends the non-review nodes to Groq. Health (`GET /api/planner/health`) reports whether keys are present. It must not return key values.

### Spoken descriptions

`SARVAM_API_KEY` is read by the Next.js route `POST /api/speech`. Do not put it only on `planner-api`. The planner service never transcribes.

`/api/speech` is not matched by the `/api/planner/*` rewrite, so the audio stays on `web`. A 30-second clip is well under the 4.5 MB request-body limit. The browser stops the recording at 30 seconds, and the route rejects anything over 2 MB.

Leave the key empty and the wizard still plans from typed text. `POST /api/speech` then returns 503 and does not call Sarvam. The route must not log the key, the audio, or the transcript.

## Steps

1. **Gate locally.** From the repo root, with the 3.12 virtualenv:

   ```powershell
   .venv\Scripts\python scripts\check_deploy.py
   .venv\Scripts\python scripts\build_db.py
   .venv\Scripts\python -m pytest
   .venv\Scripts\python -m ruff check src tests scripts services
   npm run lint
   npm run build
   ```

   `check_deploy.py` confirms the two services, the SQLite build command, the 300-second duration, the `/api/planner` rewrite, that `.env.example` names every variable the API reads, and that `SARVAM_API_KEY` is documented and `/api/speech` is not rewritten to the planner. GitHub Actions already runs this on push and pull request (`.github/workflows/ci.yml`).

2. **Link one Vercel project** to this repo. Root directory is the repository root, not `apps/web`. `vercel.json` at the root is what defines both services. Do not create a second Vercel project for the API.

3. **Add environment variables** for Preview and Production from the table above. Preview can ship with empty model keys. Production gets the Ollama and Groq secrets.

4. **Deploy a preview** from a non-production branch (Git integration) or `vercel` from the linked root. Confirm both services built: the web build is `next build` under `apps/web`, and the API build ran `python scripts/build_db.py`.

5. **Smoke the preview** the way a user would:

   - `GET /api/planner/health` returns `status: ok`, `database: true`, and key flags without secret values.
   - Open the site. Run **Example**. The timeline advances through parse, research, logistics, budget, review, and finalize. The itinerary and budget render. JSON and Markdown download.
   - Run **Future Museum**. Museum of the Future is dropped and the revision shows up.
   - Send a request with no trip length. The clarification prompt appears in the same session. Refreshing the page is not expected to resume that run.
   - Confirm `OLLAMA_BASE_URL` is not localhost and that no response writes a file on the server.
   - Open `/audit`, choose **Try a sample that should fail**, and confirm the page names places it cannot find and a cost above the pasted budget. The check is `POST /api/planner/audits` and does not need model keys.
   - Open `/plan`. **Speak** is next to **Fill in my details**. With `SARVAM_API_KEY` empty, speaking returns a message that typing still works, and `POST /api/speech` is 503. With a key set, a clip of 30 seconds or less returns a transcript in the description box. The planner run starts only after the visitor continues through the wizard.

6. **Promote to production** only after that preview passes. `vercel --prod` or promote the preview deployment. Production uses the same build, with the real model keys.

7. **Roll back** with `vercel rollback` to the previous deployment if a production run stalls, drops the database flag, or stops streaming. Both services roll back together.

## Preview acceptance

| Check | Pass |
| --- | --- |
| Health | `database: true`. Stub mode when both model keys are empty. |
| Example preset | Streamed events, a finished itinerary, provenance on cost lines, a download. |
| Future Museum preset | Closed/reopening place removed and a revision recorded. |
| Missing days | Clarification in the same browser session. |
| Offline data | `USE_LIVE_APIS=false`. Routing and weather come from the seed. |
| Audit page | `/audit` sample reports unknown places and does not require `OLLAMA_API_KEY` or `GROQ_API_KEY`. |
| Secrets | Keys absent from logs, the health body, and the client bundle. `SARVAM_API_KEY` is absent from the browser bundle. |
| Speech | `/plan` shows **Speak**. Empty key: 503 from `/api/speech`, typing still works. Set key: a clip no longer than 30 seconds becomes text in the same box. |
| Duration | The example run finishes inside 300 seconds, including cold start. |

## If the preview fails

| Symptom | What to check |
| --- | --- |
| `/api/planner/health` is 404 | Rewrite order in `vercel.json`. `/api/planner/(.*)` must target `planner-api` and sit above the catch-all to `web`. |
| Health says `database: false` | The API build did not run `scripts/build_db.py`, or the sqlite file was not included. The API looks at `data/dubai.sqlite`, then `services/planner-api/dubai.sqlite`. |
| Build fails installing Python | Python 3.12, install from `services/planner-api/requirements.txt` (`-e ../..` → root `pyproject.toml`). The machine default 3.15 cannot install LangGraph. |
| Function exceeds the size limit | Remove unused provider packages first (`langchain-google-genai` if Gemini is unused). A container image is the next step, not a second host. |
| Run dies around 300 seconds | Cap revisions, keep `USE_LIVE_APIS=false`, and confirm the UI is consuming the SSE stream rather than waiting for one JSON body. |
| Services beta will not start the Python service | Fall back to one project and one Python function, same URL prefix. Keep the Next.js app as the only public UI. |
| Models never run in production | `OLLAMA_API_KEY` and `GROQ_API_KEY` are set on Production, and `OLLAMA_BASE_URL` is `https://ollama.com`. |
| Speak does nothing useful | `SARVAM_API_KEY` is set on the web service, not only on `planner-api`. The recording is 30 seconds or shorter. A 503 means the key is missing, and typing is the fallback. |

## Later, only if the product needs it

These are not part of the first deploy.

- **Shared cache** for routes and weather: set `CACHE_STORE_URL` to an external store (Upstash Redis or Vercel Runtime Cache). Pick a Marketplace store when this is actually required.
- **Durable resume** across refresh or a second request: set `CHECKPOINT_STORE_URL` (Neon, Turso, or Redis). Until then, `POST /api/planner/runs/{run_id}/resume` is not a cross-request guarantee.
- **Live maps and external APIs:** `ORS_API_KEY` plus `USE_LIVE_APIS=true`, with the existing local fallback when a provider fails.
- **Larger Python image:** Vercel container image only after dependency trimming still misses the bundle limit.

## Out of scope

Booking, live prices, flights, multi-city trips, user accounts, and a map view. None of those add a deployable service.
