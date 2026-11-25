# Dubai AI Travel Planner — Multi-Agent Systems

Project context for a Dubai-focused AI travel planner that turns a natural-language request into a personalized, budget-conscious, practical itinerary. Planning is split across specialized agents, orchestrated with LangGraph, and deployed as a Vercel-native web application.

The goal is to show how multi-agent architectures solve a real planning problem through coordinated decision-making. This is a technical prototype, not a commercial booking platform.

The same rules also power an itinerary auditor at `/audit`. A visitor pastes a Dubai plan from a general chatbot. The auditor matches place names to the curated catalog, prices and routes only the matches, and runs the budget and review rules. The page states what failed, in plain language, and shows a rebuilt plan when the usable places are enough to make one. That is the public proof that a fluent itinerary is not the same as a checked one.

On the plan wizard, the same description can be typed or spoken. Speech is a second way to fill that box. It is not another planning agent. A recording stops at 30 seconds, Sarvam Saaras turns it into text, and the visitor edits the text before the wizard reads it. Typing still works when the microphone or the Sarvam key is unavailable.

Locked product defaults: [decisions.md](./decisions.md). Architecture: [architecture.md](./architecture.md). Runtime sequence: [sequencediagram.md](./sequencediagram.md). Data research and delivered catalog: [research.md](./research.md). Phased work: [implementationplan.md](./implementationplan.md).

---

## 1. Background

Planning a trip involves interconnected decisions:

- Selecting attractions
- Finding accommodation
- Organizing transportation
- Estimating expenses
- Matching the itinerary to the traveler's preferences

A traditional chatbot can emit an itinerary in one response. It does not necessarily verify travel times, check budget constraints, or validate recommendations against external information.

This project explores how multiple specialized AI agents collaborate on that problem, orchestrated as a LangGraph workflow.

---

## 2. Problem Statement

Build a Dubai-focused AI Travel Planning System that converts a natural-language travel request into a personalized, budget-conscious, and practical travel itinerary.

Instead of one agent, the system divides planning among specialized agents for:

- Destination research
- Logistics
- Budgeting
- Quality validation

The application is built with LangGraph and hosted on Vercel: graph-based orchestration, shared state, parallel execution, conditional decisions, a review-feedback loop, and a web UI that streams agent progress from Vercel-hosted APIs.

### 2.1 Entering the request

The plan wizard at `/plan` collects the request in steps, and it also offers one free-text description. That description can be typed or spoken. Both paths land in the same text box.

- **Speak** records from the microphone for at most 30 seconds. That cap is the limit of Sarvam's synchronous speech-to-text API (`POST https://api.sarvam.ai/speech-to-text`, model `saaras:v4`, mode `transcribe`).
- The browser posts the clip to `POST /api/speech` on the Next.js app. `SARVAM_API_KEY` stays on that route. The planner API never receives the audio.
- The transcript is written into the description box, after any text that was already there. The visitor can edit it, then choose **Fill in my details**. That button is the existing extractor. Speech does not skip it and does not start a planner run.
- A denied microphone, a browser that cannot record, an empty Sarvam key, or a failed transcription leaves the typed box working. The server does not store the audio.

The structured extractor looks for English phrases such as days, an AED amount, who is travelling, and interests. A transcript in another language still appears in the box for editing. The visitor can rephrase it before filling the steps.

---

## 3. Example User Request

> Plan a 4-day trip to Dubai with a budget of AED 5,000, excluding flights. I enjoy cultural attractions, local food, and beaches. I prefer affordable hotels and want to avoid crowded places.

The system should generate:

- A personalized day-by-day itinerary with suggested timings
- Recommended attractions, restaurants, and accommodation areas
- Transportation options and estimated travel durations
- A category-wise budget breakdown in AED
- Alternatives when the proposed itinerary exceeds the budget
- A final itinerary validated against the user's preferences and constraints

---

## 4. Multi-Agent System Design

### Agent 1 — Orchestrator

Understands the travel request, extracts constraints, coordinates specialized agents, manages dependencies, and assembles the final itinerary.

### Agent 2 — Destination Research

Researches Dubai attractions, restaurants, cultural experiences, and neighborhoods. Recommends activities based on user interests, location, and preferences.

### Agent 3 — Logistics

Suggests accommodation areas, calculates distances and travel times, identifies transportation options, and organizes activities into a practical geographical sequence.

### Agent 4 — Budget

Estimates accommodation, food, transportation, and activity costs. Calculates total projected expenditure and recommends alternatives when costs exceed the budget.

### Agent 5 — Review

Evaluates the complete itinerary for:

- Budget compliance
- Schedule feasibility
- Preference alignment
- Duplicate activities
- Missing information
- Closed or non-operational places
- Holiday effects (Ramadan meals, Eid heritage holds, National Day crowds)

Requests revisions when necessary.

---

## 5. Dubai Travel Data — Sources and Integration

The system combines a curated Dubai dataset (the source of truth) with optional **free** APIs that do not require a payment card.

Paid and card-gated services (including the Google Maps Platform) are out of scope. Discontinued services (including the Amadeus Self-Service hotel APIs, closed on 2026-07-17) are not used.

Phase 1 is complete. Implementation uses the committed seed in `data/seed/`, not the original curation targets. Inventory and gaps: [implementationplan.md](./implementationplan.md) section 1.7, [research.md](./research.md) section 1.2, [decisions.md](./decisions.md).

| Data requirement | What the seed actually contains | Usage |
| --- | --- | --- |
| Attractions | 81 places across eight planning areas, mostly `estimated`. Tags meet the interest floors. Museum of the Future is `reopening` | Research attractions and neighborhoods. Never schedule `closed` / `reopening` places |
| Ticket price, closure, timed entry | Every place has a price range, `operational_status`, and `timed_entry`. Almost none are official-site quotes | Activity cost lines and review rules |
| Restaurants | 80 rows, 10 per area, lunch + dinner. `cuisine` is `unspecified`. No menu prices | Meals by area and `price_band`, not cuisine |
| Routes and transportation | 64 Metro/tram stations, 65 edges with estimated minutes, two tram–metro walks. Station `zone` is empty. No GTFS. OpenRouteService is optional at runtime (`ORS_API_KEY` unset) | Offline graph, then straight line. Live ORS/OSRM in Phase 5 if a key is registered |
| Public transport fares | 20 RTA/Nol rows. Silver 1/2/3+ is `verified`. 1-day pass, taxi, and Abra are `estimated`. No bus table | Budget transport. Zone span from a planner-side area map |
| Accommodation | 32 hotels, every area has budget / mid / luxury. Nightly peak and summer bands are estimated. `stars` is empty | Stay options via `Hotel.stay_option`. No live hotel API |
| Activity and food costs | Place `price_aed` plus `price_bands.json` (food, activity, coffee, water, typical taxi) | Deterministic budget lines |
| Weather | 12-month Open-Meteo archive in `climate.json` (July mean high 41 °C). Live forecast optional | Heat avoidance and indoor/outdoor scoring |
| Holidays | 14 city-wide 2026–2027 rows. Ramadan drops lunch. Eid holds heritage on day one and raises crowds. National Day raises crowds | Sequencing and review, not a per-place closure list |

### Data integration approach

- The curated JSON / SQLite catalog is the source of truth and must work with every external API off.
- Wikidata and Nominatim were curation-only. The planner never calls them at runtime.
- Most catalog prices are `estimated`. Silver Nol fares that match the RTA table are `verified`. Record `source` and `as_of` on every row.
- OpenRouteService (OSRM fallback) is used for road times only when a free key is configured and `USE_LIVE_APIS` is on. Otherwise use the transit graph, then straight line.
- Overpass may enrich restaurant cuisine or hours at runtime later. It must not replace curated prices, `operational_status`, or hotel nightly ranges.
- Open-Meteo forecast is optional; `climate.json` is the offline fallback.
- Runtime cache and durable checkpoints stay off unless store URLs are set ([decisions.md](./decisions.md)).
- Live hotel bookings, ticket purchases, guaranteed real-time prices, and any paid or card-gated APIs are outside scope.

---

## 6. LangGraph Orchestration

Implement the agents as nodes in one stateful LangGraph. The graph should demonstrate:

- Parallel research (Destination Research and Logistics)
- Shared state across nodes
- Conditional routing
- A review-feedback loop that triggers itinerary revisions
- Task delegation and synthesis of each agent's findings into one structured itinerary

---

## 7. End-to-End Workflow

```
Typed description, or a spoken clip of at most 30 seconds
        |
        v
 Text in the plan wizard (the visitor can edit it)
        |
        v
User Travel Request
        |
        v
 Parse Requirements
        |
        v
   Orchestrator
        |
        +-------------------+
        |                   |
        v                   v
 Destination Agent     Logistics Agent
        |                   |
        +---------+---------+
                  |
                  v
             Budget Agent
                  |
                  v
              Review Agent
                  |
           +------+------+
           |             |
         Pass          Revise
           |             |
           v             |
     Final Itinerary <---+
```

The Vercel-hosted application should also display:

- Which agent is executing
- What information it produces
- How the overall plan changes during review

Execution order implied by the workflow:

1. On `/plan`, take a typed description or a spoken clip of at most 30 seconds. Speech becomes text in the same box and does not start the graph.
2. Parse the user's natural-language request into constraints.
3. Orchestrator coordinates Destination Research and Logistics (these can run in parallel).
4. Budget Agent estimates costs from the combined plan.
5. Review Agent checks constraints.
6. On pass, return the final itinerary. On revise, loop back and update the plan.

---

## 8. Technology Stack

| Layer | Choice |
| --- | --- |
| Development environment | Cursor |
| Programming language | Python for the LangGraph planner, TypeScript/React for the Vercel UI |
| Multi-agent framework | LangGraph running behind Vercel-hosted API endpoints |
| LLM | Ollama Cloud (`nemotron-3-nano`) for every LLM node except `review` (Groq `openai/gpt-oss-20b`). `LLM_PROVIDER=groq` also sends the other nodes to Groq |
| Frontend | Next.js / React at `apps/web`, deployed on Vercel. Map view is post-MVP |
| Speech to text | Optional Sarvam Saaras v4, called only by `POST /api/speech`. Recordings stop at 30 seconds. An empty `SARVAM_API_KEY` leaves typing in place |
| Backend/API | Vercel Services: `web` + `planner-api` (Python FastAPI). Fallback: one project with a Python function. Public path `/api/planner/*` |
| Data | Static JSON / read-only SQLite in `data/seed/` (counts and gaps in implementation plan 1.7). Optional **free** runtime APIs: OpenRouteService, Overpass, Open-Meteo |
| Runtime persistence | Off unless `CACHE_STORE_URL` or `CHECKPOINT_STORE_URL` is set. No Marketplace store chosen yet |
| Validation | Pydantic schemas and rule-based budget, holiday, and itinerary checks |

---

## 9. MVP Scope and Success Criteria

**Initial scope**

- Destination: Dubai only
- Trip length: 1–7 days
- Currency: AED
- Out of scope: live hotel bookings, ticket purchases, guaranteed real-time prices, flights (example request excludes flights), paid or card-gated APIs (Google Maps Platform, paid LLM APIs), and discontinued hotel APIs (Amadeus Self-Service)

**Success criteria**

The project is successful when it can:

1. Accept natural-language travel requirements and produce a structured Dubai itinerary.
2. Demonstrate meaningful collaboration among specialized agents.
3. Generate realistic travel schedules and estimated budgets using available data.
4. Detect and revise at least one itinerary constraint violation.
5. Visualize which LangGraph node is executing and how shared state changes through the graph.
6. Check a pasted itinerary from another AI: name unknown places, flag broken rules, and show a rebuilt version when the usable places are enough.
7. Accept a spoken trip description of up to 30 seconds, show the transcript in the same box as typed text, and keep planning available when speech is off or fails.

**Expected outcome**

A working, interactive Vercel deployment that helps technical and nontechnical audiences understand agent specialization, orchestration, collaboration, shared context, and validation through a practical travel-planning use case.

---

## Constraints to preserve in implementation

- One LangGraph owns orchestration: agents are nodes, trip state is shared, and the review node can route back for revision.
- Shared context across agents, managed by the Orchestrator node.
- Review must be able to reject a plan and trigger a revision, not only approve it.
- Budget is total for the group. Accommodation is inside the budget even when the user only excludes flights. Defaults are recorded as assumptions ([decisions.md](./decisions.md)).
- Costs are estimates. Label verified facts, API-derived results, and estimates separately. Most seed prices are `estimated`.
- Local curated data must work when external APIs are unavailable. Do not invent cuisines, hotel stars, or Nol zones that the seed does not have.
- Catalog and map data stay on free sources. No Google Maps Platform and no discontinued hotel APIs. Non-review LLM calls use Ollama Cloud (`nemotron-3-nano`). Review uses Groq `openai/gpt-oss-20b`.
- Vercel functions are stateless. Do not write cache, checkpoints, or exports to the deployed filesystem. Durable resume and runtime cache stay off unless store URLs are set.
- The deployed demo calls Ollama Cloud (`https://ollama.com`) for every LLM node except `review`. Review calls Groq `openai/gpt-oss-20b`. A missing `OLLAMA_API_KEY` or `GROQ_API_KEY` leaves that provider's Phase 3 stubs in place. Do not point production at a localhost Ollama server.
- Spoken input is optional and capped at 30 seconds. The browser records the clip and `POST /api/speech` forwards it to Sarvam. The key never reaches the browser, the audio is not written to disk, and the planner graph is unchanged. A missing `SARVAM_API_KEY` only disables the microphone path.
