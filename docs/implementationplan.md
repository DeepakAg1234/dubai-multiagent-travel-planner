# Implementation Plan — Dubai AI Travel Planner (LangGraph)

Derived from [architecture.md](./architecture.md) (section 16 phases) and [problemStatement.md](./problemStatement.md). Data sourcing is in [research.md](./research.md). Product defaults are in [decisions.md](./decisions.md).

Each phase lists goals, tasks, deliverables, tests, and an exit check. Phases are sequential, with the noted parallelizable work. Estimates assume one developer.

---

## Overview

| Phase | Name | Est. | Depends on | Maps to success criteria |
| --- | --- | --- | --- | --- |
| 0 | Environment and decisions | 0.5 d | none | n/a |
| 1 | Foundations (skeleton, models, data) | done | 0 | 3 |
| 2 | Deterministic core | 2-3 d | 1 | 3, 4 |
| 3 | Graph skeleton (stubbed LLM) | 2 d | 1, 2 | 2, 4, 5 |
| 4 | LLM agents | 3-4 d | 3 | 1, 2 |
| 5 | Live data adapters | 2-3 d | 1 (can overlap 4) | 3 |
| 6 | Vercel UI and planner API | 4-5 d | 3 (finish after 4) | 5 |
| 7 | Hardening, evaluation, deployment docs | 2-3 d | all | 1-5 |

Total remaining after Phase 1: about 15-20 working days. Phase 2 onward is written against the committed seed in `data/seed/` (counts and gaps in section 1.7), not the original curation targets.

Guiding rules for every phase:

- LLMs reason, code calculates. Prices, totals, and checks are deterministic Python.
- Every fact carries provenance (`verified`, `api`, `estimated`).
- Only free sources, no payment card. Offline mode must always work.
- Vercel deployment is stateless. Runtime cache, exports, and LangGraph checkpoints cannot depend on local filesystem writes.
- Tests ship with the code. No phase is done until its exit check passes.

---

## Phase 0 — Environment and Decisions

**Goal:** Resolve blocking open questions and prepare the workspace.

Tasks:

1. Create the Python environment (3.12+) and `pyproject.toml` with: `langgraph`, `langchain-core`, `langchain-groq`, `langchain-google-genai`, `langchain-ollama`, `pydantic`, `pydantic-settings`, `fastapi`, `uvicorn`, `httpx`, `pytest`, `pytest-cov`, `ruff`, `mypy`.
2. Create the Vercel web environment with `package.json`, Next.js, React, TypeScript, linting, and a local dev script.
3. Decide the deployed LLM providers: Ollama Cloud (`nemotron-3-nano`) for every LLM node except `review`, which uses Groq `openai/gpt-oss-20b`. `LLM_PROVIDER=groq` also sends the non-review nodes to Groq.
4. Register a free OpenRouteService key (optional at this stage).
5. Lock the open-question defaults from architecture section 18: budget is total for the group, accommodation is inside the budget, the map view is optional (post-MVP), and durable resume is optional unless an external checkpoint store is configured.
6. Choose the deployment shape: Vercel Services (`web` + `planner-api`) is preferred; a single project with a Python API function is acceptable if simpler.
7. Initialize git, `.gitignore` (including `.env`, `.env.local`, generated SQLite, local caches), `.env.example`, and `vercel.json` or `vercel.ts`.

Deliverables: `pyproject.toml`, `package.json`, `.gitignore`, `.env.example`, initial Vercel config, a short `docs/decisions.md` (optional).

Exit check: `pytest` runs (empty suite), `python -c "import langgraph"` succeeds, `npm run lint` or `npm run build` reaches the expected empty-app baseline.

---

## Phase 1 — Foundations

**Goal:** Skeleton, typed models, and a validated local dataset.

### 1.1 Project skeleton

Create the structure from architecture section 15:

```
apps/web/{app,components,lib}/
services/planner-api/{api,src/travel_planner}/
src/travel_planner/{config.py, state.py, llm.py, service.py}
src/travel_planner/{models,graph/nodes,tools,data/local,data/providers,rules}/
scripts/ prompts/ data/seed/ tests/
```

Keep the Python package importable from tests and from the planner API service. The package can start at the repo root and be moved under `services/planner-api` before deployment if that makes Vercel service configuration simpler.

### 1.2 Configuration

- `config.py` with `pydantic-settings`: `LLM_PROVIDER`, `OLLAMA_API_KEY`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `GROQ_API_KEY`, `GROQ_MODEL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `ORS_API_KEY`, `USE_LIVE_APIS`, `MAX_REVISIONS` (default 3), `BUFFER_PCT` (default 10), per-run API call budget, cache/checkpoint store URLs if enabled.
- Missing keys disable the related provider rather than raising.
- `.env.example` documents both local and Vercel environment variable names. Vercel dashboard/project env vars are the production source of truth.

### 1.3 Pydantic models (`models/`)

Implement from architecture section 5: `Provenance`, `Sourced`, `Constraints`, `Place`, `StayOption`, `TransportOption`, `Leg`, `Slot`, `DayPlan`, `Itinerary`, `BudgetLine`, `BudgetReport`, `Alternative`, `Violation`, `ReviewReport`, `PlanBrief`, `Candidates`, `AgentEvent`, `ToolResult[T]`.

### 1.4 Shared state

`state.py`: `TripState` TypedDict with reducers (`operator.add`) for `excluded_ids`, `events`, `warnings`.

### 1.5 Seed dataset

Build JSON seed files in `data/seed/`, each row with `source` and `as_of`. The table below is the original target. What shipped is in section 1.7.

| File | Target size | Requisite sources |
| --- | --- | --- |
| `places.json` | 80-120 attractions, beaches, cultural sites, and markets. Floors: culture 15-20, landmarks 10-15, beaches and outdoor 10-15, malls 8-10, family 8-10, nightlife 6-8, free or very cheap 15-20. Fields include crowd level, visit minutes, hours, indoor flag, `timed_entry`, and `operational_status` | Visit Dubai and Wikidata for the named list and official URL. Overpass for coordinates, category, `fee`, and hours. Each attraction's official site for price, closure, and timed entry |
| `restaurants.json` | 80-120, about 6-8 in each planning area, across budget, mid, and upscale | Visit Dubai dining and neighborhood pages, then a per-area Overpass extract (`cuisine`, `opening_hours`, coordinates). Price tier is `estimated` unless a menu price is recorded |
| `hotels.json` | 30-40: two per major area for each supported tier, with a peak and a summer nightly range | Data.Dubai, Wikidata, and Overpass for name, coordinates, and stars. Each hotel's official site for the nightly range |
| `transit_stations.json`, `transit_edges.json` | All Metro and tram stations, plus a ride time on each segment used for sequencing | RTA open data or GTFS. If no GTFS feed is published, Overpass route relations for station order and estimated minutes |
| `fares.json` | RTA Nol fare rules (Silver card, 1-day and 7-day passes) | RTA fare pages |
| `price_bands.json` | Food and activity AED ranges per tier | Observed menus and RTA taxi tariffs |
| `climate.json` | 12 monthly rows | Open-Meteo archive, checked once and stored |
| `holidays.json` | 10-24 city-wide rows for the next year or two: Ramadan, Eid, and fixed public holidays. Islamic dates stay `estimated` until an official announcement. Effects are category rules (`drop_lunch`, `heritage_may_close_first_day`, `high_crowd`), not a per-place closure list | UAE government holiday list for fixed dates. FAHR circulars once issued. Expected Hijri dates labeled estimated |

Every planning area (Old Dubai, Downtown, Marina / JBR, Jumeirah, Al Quoz, Palm, Dubai Creek, Business Bay) needs places, meals, and at least one hotel per supported tier. Wikidata and Nominatim are curation-only. Nominatim fills a coordinate only when Wikidata and Overpass have none. Mark closed or reopening places (for example Museum of the Future) so the review rule has real data. Record `source` and `as_of` on every row.

### 1.6 SQLite build and repositories

- `scripts/build_db.py`: validate seed JSON against Pydantic, then load into `data/dubai.sqlite`.
- `data/repository.py`: Protocols (`PlaceRepo`, `RestaurantRepo`, `HotelRepo`, `TransitRepo`, `FareRepo`, `PriceRepo`, `ClimateRepo`, `HolidayRepo`).
- `data/local/`: SQLite implementations.

Tests: model validation, seed schema validation, repository queries (filter by area, tag, tier, status).

Exit check: `python scripts/build_db.py` succeeds and all seed rows validate. Repository tests pass.

### 1.7 Delivered catalog (locked for later phases)

Phase 1 is complete. Phases 2–7 consume this committed dataset through the repository protocols. Do not re-curate inside later phases; treat gaps as planner constraints.

| File | Count | Facts the rest of the plan must use |
| --- | --- | --- |
| `places.json` | 81 | 64 rows are in the eight `PLANNING_AREAS`. 17 are in satellite areas that have no hotels and no restaurants: Dubailand 5, Zabeel 2, Al Barsha 2, and one each in Al Mamzar, Al Qudra, Mushrif, Jebel Ali, Dubai Hills, Mirdif, Meydan, and Expo. Tags: culture 15, landmark 16, outdoor 33, shopping 25, family 9, beach 8, nightlife 6, food 1. `mall` is a category (9 rows), not a tag. Free or cheap (`max_aed` ≤ 20) is 57. Heritage categories are `museum`, `mosque`, `gallery`. Crowd categories are `mall`, `beach`, `park`, `theme_park`, `water_park`, `viewpoint`, `landmark`. `Museum of the Future` is `reopening` as of 2026-09-01. 13 timed-entry rows. Hours keys are `mon`…`sun` or `daily`; values include clock ranges, `24 hours`, and `daylight`. Business Bay has 3 places, Al Quoz and Dubai Creek 5 each. The three Dubailand theme parks and Ski Dubai (Al Barsha) carry the `family` tag and sit outside the eight areas. One `verified` row: Dubai Frame's adult ticket. The other 80 places are `estimated`. |
| `restaurants.json` | 80 | 10 per planning area only (4 budget, 4 mid, 2 upscale). No rows outside those eight areas. Every row is lunch + dinner, hours `12:00-00:00` all week. `cuisine` is `unspecified`. No menu `price_aed`; food cost comes from `price_bands.json`. All `estimated`. |
| `hotels.json` | 32 | Every planning area has budget, mid, and luxury. There are no hotel rows outside those eight areas. Nightly ranges are estimated per hotel, not one shared number per tier, and not hotel-site quotes. `stars` is empty. 24 rows have `metro_nearby`, and that field is a station name (for example `Burj Khalifa/Dubai Mall`), not a `transit_stations` id. Eight hotels have it null, including the only Jumeirah budget hotel and both Palm mid and luxury hotels. Use `Hotel.stay_option(season)` for peak vs summer. Cheapest budget peak night is AED 170; cheapest summer night is AED 120. |
| `transit_stations.json` | 64 | Red 33, Green 18, Tram 11, Union and Burjuman as `Red,Green`. `zone` is empty on every station. Interchanges: Union, Burjuman. |
| `transit_edges.json` | 65 | Directed hops with estimated minutes. Two 6-minute walk links: Tram JLT ↔ Metro DMCC, Tram Dubai Marina ↔ Metro Sobha Realty. Not an RTA GTFS feed. |
| `fares.json` | 20 | Verified Silver Nol 1 / 2 / 3+ = AED 3 / 5 / 7.50; Gold double; Red Ticket 4 / 6 / 8.50; Silver 7-day 50 / 80 / 110. Estimated: 1-day pass AED 20, Red Ticket purchase, taxi flag / km / minimum, Abra AED 1. No bus table. |
| `price_bands.json` | 10 | Food budget 25–45, mid 70–140, upscale 180–400. Activity free / budget / mid / upscale. Coffee, water, typical taxi trip 12–45. All `estimated`. |
| `climate.json` | 12 | Open-Meteo archive 2016–2025 at 25.2048, 55.2708. July mean high 41 °C. Climatology, not a forecast. |
| `holidays.json` | 14 | 2026–2027 city-wide rows. Ramadan `drop_lunch` runs 2026-02-18–2026-03-19 and 2027-02-08–2027-03-09, so 2026-03-19 is both the last Ramadan day and Eid al-Fitr day one. Eid rows carry `heritage_may_close_first_day` + `high_crowd`; the first day is the range start (2026-03-19, 2026-05-26, 2027-03-09, 2027-05-15), not every day in the range. National Day is 2–3 December in both years, with `high_crowd` on both days. New Year, Islamic New Year, and Prophet's Birthday have empty `effects`. Islamic dates other than the 2026 Eid al-Fitr row are `estimated`. Effects live in `rules/holidays.py` (`places_for_day`, `restaurants_for_day`, `apply_day_notes`). |

Locked helpers already in the tree: `HolidayRepo`, `ClimateRepo`, `DayPlan.holiday_note`, `Hotel.stay_option`, `PLANNING_AREAS`.

---

## Phase 2 — Deterministic Core

**Goal:** All calculation and checking logic works with no LLM, against the Phase 1 catalog.

### 2.1 Budget calculators (`rules/budget.py`)

- Accommodation: `hotel.stay_option(season)` × nights. Season is `summer` for May–September (inclusive), otherwise `peak`. Use the range midpoint unless a later node pins a single figure. Copy the hotel row's provenance onto the line (today: `estimated`).
- Food: one meal per remaining `meal_types` on each scheduled restaurant. Price is the matching `PriceRepo` food band for `restaurant.price_band`. There is no breakfast row and no per-restaurant menu price. On a Ramadan day, `restaurants_for_day` has already dropped lunch, so do not invent a lunch line.
- Activities: `place.price_aed` × travelers. Use `max_aed` for the booked-style estimate. Skip `closed` / `reopening` places (they must not be in the draft). If a place has no ticket (max AED 0), the line is still present with total 0 so provenance is visible.
- Transport: sum of priced legs from 2.2. Compare pay-per-trip Silver fares against the 1-day pass (`red_1day`, estimated AED 20) and the Silver 7-day pass that covers the trip's zone span. Pick the cheaper option. Do not assume an unpublished daily Silver cap. Keep the 1-day pass line `estimated`.
- Buffer line from `BUFFER_PCT` (default 10%).
- Every `BudgetLine` copies provenance from the seed row or fare rule it used.
- `build_alternatives()` using real catalog IDs: cheaper hotel in the same area and tier band below; paid place → a free or cheap (`max_aed <= 20`) place in the same or neighbouring area; taxi leg → Metro/tram via the transit graph; dinner → a lower `price_band` restaurant in the same area. Each alternative states savings and the new total.
- Budget below hotel floor: cheapest budget hotel nightly (peak AED 170, summer AED 120) × nights, plus minimum food bands and buffer. Return that floor in the report instead of a silent zero plan. The example request (4 days, AED 5,000, affordable hotel) clears the floor; a fixture of AED 400 for 4 peak nights must not.

### 2.2 Fare calculator (`rules/fares.py`)

Stations have no RTA zone. Do not read `TransitStation.zone`.

- Keep a small planner-side zone map in `rules/fares.py` from planning area (or nearest station id) to Nol zone 1 / 2 / 3+, documented as `estimated` unless a later seed fill lands.
- Metro and tram pay-per-trip: Silver 3 / 5 / 7.50 by zone span. Gold and Red Ticket exist in the table but the default traveler is Silver.
- Pass comparison as above. 7-day passes are 50 / 80 / 110 for 1 / 2 / all zones.
- Taxi: daytime flag AED 5 (22:00–06:00: 5.50) + AED 2.45/km, floor AED 12. Straight-line km is enough until Phase 5.
- Creek water crossing: Abra AED 1 when both ends are Old Dubai / Dubai Creek waterfront slots.
- Walk and in-station transfer: AED 0, minutes from the graph (6 minutes on the two tram–metro walk edges).
- No bus fare rows: if a leg would be bus, treat it as Metro if a station is nearby, otherwise taxi.

### 2.3 Clustering and ordering (`rules/sequencing.py`)

- Group selected places into days by planning area. Thin areas (Business Bay 3, Al Quoz 5, Dubai Creek 5) merge with a neighbour on the same Metro line rather than producing an empty day.
- Nearest-neighbour order with 2-opt. Durations: Dijkstra on `TransitRepo.edges` (including walk interchanges and Union / Burjuman). If no path, straight-line km at a walking or taxi speed. This is the last tier of `route_leg`.
- Time windows: `typical_visit_minutes`, opening hours (`mon`…`sun` or `daily`), meal slots at remaining `meal_types`, check-in/out.
- Heat: if `ClimateRepo.month(start_month).avg_high_c >= 35` (true for Dubai summer; July is 41 °C), outdoor (`indoor is False`) activities are not scheduled 12:00–16:00; insert a rest or indoor slot instead.
- Holidays: `HolidayRepo.overlapping(start, end)`, then `places_for_day` / `restaurants_for_day` before assignment, then `apply_day_notes` so each `DayPlan.holiday_note` is set. Do not close the whole city. Eid day one holds museums, mosques, and galleries only. Ramadan drops lunch. National Day and Eid raise crowds on mall / beach / park / viewpoint / landmark / theme and water parks; those rows leave the day when `avoid_crowds` is true.
- Transfer slots from leg minutes. Timed-entry places get a note, not a fake ticket hold.

### 2.4 Review rules (`rules/review.py`)

One pure function per check, each returning `Violation`s with `route_to`:

budget compliance, day length vs pace, travel feasibility, opening hours (including holiday meal/heritage effects), operational status, duplicates, completeness (lunch optional on `drop_lunch` days), crowds, provenance, interest coverage.

Operational-status fixture: any draft that still contains `place-museum-of-the-future` is a blocker to `orchestrator_revise`.

`run_rules(state) -> ReviewReport` applies the routing precedence (plan issues beat budget issues).

Tests (no LLM, no network): table-driven tests over the real seed plus small fixtures. Cover: Silver vs 7-day pass, taxi minimum, Abra, summer vs peak hotel, Ramadan lunch drop (2026-02-18), Eid first day vs later Eid day (2026-03-19 vs 2026-03-20), National Day crowds (2026-12-02), Museum of the Future rejected, Business Bay day merged, heat rest in July. Target above 90% coverage of `rules/`.

Exit check: unit tests pass with no network and no LLM.

---

## Phase 3 — Graph Skeleton (Stubbed LLM)

**Goal:** The full LangGraph topology runs end to end with fake agents, proving routing, parallelism, and loops, on the Phase 1 SQLite catalog.

Tasks:

1. `graph/nodes/`: one file per node from architecture section 3 (`parse_request`, `orchestrator_plan`, `destination_research`, `logistics_prelim`, `logistics_sequence`, `budget`, `budget_adjust`, `review`, `orchestrator_revise`, `finalize`, `ask_user`). LLM parts return fixed structured data built from real seed IDs (for example Old Dubai culture + a Jumeirah beach, a budget hotel with `metro_nearby`, lunch/dinner from that area). Deterministic parts call Phase 2 code.
2. `graph/routing.py`: `route_after_review`, clarification routing after `parse_request`. `revision_count` increments inside revise nodes.
3. `graph/build.py`: assemble the `StateGraph`:
   - parallel fan-out `orchestrator_plan` to `destination_research` and `logistics_prelim`, then join, then `logistics_sequence`;
   - `ask_user` via LangGraph interrupt;
   - in-memory checkpointer for a single local run, recursion limit, per-node timeouts.
4. Every node appends `AgentEvent`s (start, end, error, revision) with a state delta summary.
5. `service.py`: `PlannerService.run(request)` is a generator yielding `AgentEvent`s from `graph.stream(stream_mode=["updates","custom"])`. It does not expose LangGraph types.
6. `api/`: a thin FastAPI app with an initial streaming endpoint that converts `AgentEvent`s to SSE. Keep the API boundary free of UI assumptions.
7. `tools/`: thin agent-facing wrappers returning `ToolResult` over the repositories (local only). Wire `search_attractions`, `search_restaurants`, `search_hotels`, `get_transport_options`, `fare_calculator`, `price_lookup`, `route_leg` (graph + straight line), `get_weather` (climate table), and holiday lookup. `search_restaurants` filters by area, `price_band`, and `meal_types` only — `cuisine` is not usable.
8. Demo scenario flags: `force_revision` using catalog facts, not invented venues. Options: tighten budget below a mid-tier stay; inject `place-museum-of-the-future`; pin `start_date` to 2026-03-19 (Eid) or 2026-12-02 (National Day) with `avoid_crowds`.

Tests (fake LLM): four graph paths, each loading `data/dubai.sqlite`:

1. Pass on first review (open places only, dates off the holiday calendar).
2. Budget revise, `budget_adjust` loop, then pass.
3. Plan revise, `orchestrator_revise` loop, then pass (closed/reopening place or crowd/holiday conflict).
4. Max-iterations exhausted, finalize with warnings.

Also: parallel nodes do not conflict on state, the interrupt/resume path works, and `AgentEvent` order is correct.

Exit check: all four graph paths pass. `draw_mermaid()` renders the expected topology.

---

## Phase 4 — LLM Agents

**Goal:** Replace stubs with real prompts and structured output, grounded in the catalog.

Tasks:

1. `llm.py`: provider factory. `review` uses Groq (`ChatGroq`, model `openai/gpt-oss-20b`); every other LLM node uses Ollama Cloud (`ChatOllama`, model `nemotron-3-nano`). `LLM_PROVIDER=groq` also sends those nodes to `ChatGroq`. Temperature settings per node type, retry with backoff, per-node call and token counters. Follow `docs/decisions.md`: a missing Ollama or Groq key leaves that provider's stubs in place.
2. Structured-output helper: validate with Pydantic, one repair retry with the validation error, then a deterministic fallback per node.
3. `prompts/`: versioned templates for each LLM node. Grounding rules: use only provided IDs, never invent prices or cuisines, never reopen `operational_status` of `closed` / `reopening`, and surface uncertainty (`estimated` is the common case). Place `source` text goes in delimited data fields (prompt-injection defense).
4. Implement node logic:
   - `parse_request`: extract `Constraints`, apply defaults (total group budget, accommodation inside, flights excluded, balanced pace, 1 traveler) and record assumptions, flag missing critical fields (triggers `ask_user`).
   - `orchestrator_plan` / `orchestrator_revise`: produce `PlanBrief` (per-day themes, crowd hints). Hotel and meal areas come from `PLANNING_AREAS`. A day may also name a satellite area when the shortlist place lives there (Dubailand, Al Barsha, Zabeel, and the other areas in 1.7). Do not put a heritage theme (`museum`, `mosque`, `gallery`) on an Eid first day: 2026-03-19, 2026-05-26, 2027-03-09, 2027-05-15. When `avoid_crowds`, do not theme a day around crowd categories (`mall`, `beach`, `park`, `viewpoint`, `landmark`, `theme_park`, `water_park`) on a `high_crowd` day. National Day is both 2 and 3 December. 2026-03-19 is also inside Ramadan, so that day drops lunch as well as heritage. New Year, Islamic New Year, and Prophet's Birthday do not close venues. Revise reads `ReviewReport` and sets `excluded_ids`, theme changes, pace shifts.
   - `destination_research`: deterministic scoring to a shortlist, then LLM picks and explains from the shortlist. Score with tags (`culture`, `outdoor`, `shopping`, `beach`, `family`, `nightlife`, `landmark`), `crowd_level`, `indoor` vs climate heat, `operational_status == open`, and `excluded_ids`. `shopping` is broader than category `mall` (markets and neighbourhoods carry it too). A `food` interest is satisfied by restaurants, not place tags (`food` appears once). Restaurants exist only in the eight planning areas: filter by area + `price_band` + remaining `meal_types`. Each area has 4 budget, 4 mid, and 2 upscale. Ignore `cuisine` (`unspecified` on every row). `PlanBrief.cuisine_focus` may stay empty or mean "local / area food". Merge and de-duplicate by name and coordinates. If a planning area is too thin (Business Bay, Al Quoz, Creek), relax to its neighbour before dropping an interest. Do not drop `family` or a mall visit because the matching row is outside the eight areas: IMG Worlds, Motiongate, and Legoland are in Dubailand, Ski Dubai and Mall of the Emirates are in Al Barsha. Pair that place with a planning-area hotel and restaurant; there is no stay or meal row in the satellite area.
   - `logistics_prelim`: hotels by requested tier (`budget`, `mid`, `luxury`; default budget for "affordable"). Restaurant tiers are `budget` / `mid` / `upscale` and must not be copied onto the hotel. Prefer a hotel whose `metro_nearby` is set, but do not reject an area when the only row in that tier has it null (Jumeirah budget, Palm mid, Palm luxury). Treat `metro_nearby` as a station name, not a station id. Do not use `stars` (all null). Transport options from fare rows (Silver Metro/tram, taxi, Abra).
   - `logistics_sequence`: Phase 2 sequencing, LLM only for tie-breaks and day themes. Do not re-parse hours in the prompt; `rules/hours.py` already accepts `mon`…`sun`, `daily`, `24 hours`, and `daylight`. Persist `holiday_note`. A satellite place stays on the day, with meals and the hotel still in a planning area.
   - `budget_adjust`: apply a chosen alternative from 2.1, then recompute through `budget`.
   - `review` stage 2: LLM qualitative review that may add warnings or request revision but cannot overturn a rule blocker (including Museum of the Future and holiday effects).
   - `finalize`: narrative, provenance summary, assumptions, warnings, revision history, holiday notes. Expect places, hotels, restaurants, fares-that-are-estimated, and climate to be `estimated`. Call out the exceptions: Dubai Frame's adult ticket is the only `verified` place price, and 55 of 64 stations are provenance `api`.
5. Run the example request (4 days, AED 5,000, culture / food / beaches, affordable hotels, avoid crowds). It must not schedule Museum of the Future. A dated variant in Ramadan must omit lunch. A family-interest request may select a Dubailand theme park and must still book the hotel and meals in a planning area. A start on 2026-03-19 must omit lunch and heritage places. A start on 2026-12-03 with `avoid_crowds` must skip crowd categories the same way 2026-12-02 does.

Tests: node-level tests with stubbed LLM returning fixed catalog IDs, schema-failure and repair-retry tests, and prompt-injection fixtures (a place `source` string containing instructions). Include a shortlist that contains the Future Museum and assert the picker never selects it. Include a shortlist with `place-img-worlds-of-adventure` and assert a family request can keep it while restaurants stay in a planning area.

Exit check: 8-10 sample requests produce valid, schema-conforming itineraries offline (curated data only), and the example request satisfies the AED 5,000 budget.

---

## Phase 5 — Live Data Adapters

**Goal:** Optional free-API enrichment with safe fallback. Can overlap Phase 4. The catalog remains the source of truth.

Tasks:

1. `data/cache.py`: pluggable cache interface. Local development may use SQLite or `diskcache`; Vercel deployment must use an external store or disable runtime caching (`CACHE_STORE_URL` empty, per `docs/decisions.md`). TTLs: places 30 d, routes 7 d, weather 3 h.
2. `data/resilience.py`: retries, timeouts, circuit breaker (disable an API for the session after repeated failures), rate limiter, per-run API call budget (`api_call_budget` default 40).
3. Providers in `data/providers/`:
   - `openrouteservice.py`: matrix and directions. Keep under 40 calls per minute and the daily Matrix 500 / Directions 2,000 limits. `ORS_API_KEY` is still optional.
   - `osrm.py`: public demo fallback.
   - `overpass.py`: optional restaurant/place enrichment (cuisine, hours). Explicit `[timeout]` and `[maxsize]`, cache results, treat 429/504 as a fallback signal. Do not replace curated prices, `operational_status`, or hotel nightly ranges.
   - `open_meteo.py`: forecast for supported travel dates, with `ClimateRepo` fallback (the 12-row archive) for dates beyond range or when the API is down.
4. Tool resolution order: cache, then live API (if `USE_LIVE_APIS` and healthy), then curated data. Set `degraded=True` on fallback. Offline `route_leg` is the 64-station / 65-edge graph, then straight line. Offline weather is `climate.json`.
5. Wire `route_matrix`, `route_leg`, `search_restaurants`, `get_weather` to the layered resolver. Weather feeds research scoring (indoor/outdoor) together with the heat rule from 2.3. `search_attractions` and `search_hotels` stay local.
6. Attribution strings for OSM (ODbL) and Open-Meteo (CC BY 4.0), shown where their data appears. Wikidata is not called at runtime.

Tests: provider adapters against recorded cassettes, circuit breaker and rate limiter unit tests, an `offline` marker running the full flow with `USE_LIVE_APIS=false` on the committed SQLite file.

Exit check: the same request completes with APIs on and off. Failures degrade gracefully and are flagged. Offline mode still uses holiday effects and the transit graph.

---

## Phase 6 — Vercel UI and Planner API

**Goal:** A watchable end-to-end Vercel-native run. Starts after Phase 3 (using the fake LLM) and finishes after Phase 4.

Tasks:

1. `services/planner-api`: expose a FastAPI streaming endpoint that starts a planner run and sends `AgentEvent`s as SSE.
2. `apps/web`: Next.js input panel with free text, optional overrides (days, budget, interests, start date, hotel tier, avoid crowds), toggles for live APIs, and demo "force revision" presets tied to catalog facts (tight budget, Future Museum, Eid / National Day).
3. Live agent timeline: consume SSE events and update React state (status, duration, collapsible output summary).
4. Graph view: Mermaid render with the active node highlighted.
5. State inspector: key `TripState` slices (constraints, candidates, draft, budget, holiday notes) as they change.
6. Revision diff: before/after itinerary and budget per loop, with violations listed.
7. Result tabs: Itinerary (day cards with timings, legs, `holiday_note`, and operational-status warnings), Budget (category chart, line items, provenance badges: ✅ verified, 🌐 API, ≈ estimated — most catalog lines will be ≈), Assumptions and warnings, Map optional/post-MVP using stored `lat`/`lng`.
8. `ask_user` clarification UI. For MVP, handle resume in the same browser session; durable resume requires `CHECKPOINT_STORE_URL`.
9. LLM usage panel (calls and tokens per node versus free-tier limits). Degraded-data indicators when live routing or weather fell back.
10. Export: JSON and Markdown download, generated on demand rather than written to local disk.
11. `vercel.json` or `vercel.ts`: configure services, rewrites from `/api/planner/*` to the planner API, and any function duration settings needed for planner runs. Bundle read-only `data/dubai.sqlite` (or rebuild it in the service build). No runtime writes.

Tests: UI smoke tests for the Next.js app, API contract tests for the SSE endpoint on the fake-LLM graph, and a manual Vercel preview walkthrough.

Exit check: a local run and a Vercel preview show each node executing, state changing, and a revision loop, ending with downloadable output.

---

## Phase 7 — Hardening, Evaluation, Docs

**Goal:** Meet all success criteria with evidence, using the locked catalog.

Tasks:

1. `scripts/run_eval.py`: 8–10 requests varying days (1–7), budget, tier, interests, crowd preference, and start date. Score budget compliance, schedule feasibility, interest coverage, duplicate rate, closed-place rate, and holiday-rule adherence. Save results to track over time.
2. Edge cases, each a fixture against real rows:
   - Budget below hotel floor (4 peak nights under AED 680 before food and buffer).
   - Thin-area trip focused on Business Bay.
   - 1-day and 7-day trips (7-day pass vs pay-per-trip).
   - Missing trip length (clarification).
   - All APIs down (`USE_LIVE_APIS=false`).
   - Malformed LLM output.
   - Closed/reopening attraction requested (Museum of the Future).
   - Ramadan 2026 (`2026-02-18`) — no lunch slots.
   - Eid al-Fitr first day (`2026-03-19`) — no museum/mosque/gallery; later Eid day keeps them.
   - National Day (`2026-12-02`) with `avoid_crowds` — no mall/beach/park/viewpoint/landmark/theme-park day.
   - July start — outdoor midday rest from climate.
3. Error handling per architecture section 12: per-node timeouts, recursion limit, graceful finalize with warnings.
4. Demo scenarios: one-click forced revision (tight budget, Future Museum, or National Day crowds) and the problem-statement example.
5. Logging hygiene: no keys or full user prompts at default level. Optional LangSmith tracing.
6. Deployment checks: Vercel preview runs the fake-LLM demo, verifies streaming events, and confirms required env vars. Static seed / SQLite is bundled read-only.
7. Documentation: `README.md` (setup, `.env`, Vercel env vars, local dev, Vercel deployment, offline mode, demo script, how to rebuild the DB from `data/seed/`) and a refreshed architecture note on any deviations (empty station zones, unspecified cuisine, estimated hotel bands).
8. CI (optional): ruff, mypy, pytest (excluding live-API tests), frontend lint/build, and preview deployment checks.

### Success criteria checklist

| # | Criterion | Verified by |
| --- | --- | --- |
| 1 | Natural-language request produces a structured Dubai itinerary | Eval set plus example request |
| 2 | Meaningful multi-agent collaboration | Event timeline and state inspector show distinct node outputs |
| 3 | Realistic schedules and budgets from available data | Rule checks pass, provenance on all cost lines |
| 4 | At least one violation detected and revised | Forced-revision demo and graph path tests |
| 5 | Visible active node and state changes | Next.js timeline, graph view, state inspector |

Exit check: the checklist is all green, the eval set meets agreed thresholds (for example 100% budget compliance or flagged, 0 closed places, no duplicates), and a fresh clone runs offline using the README steps.

---

## Itinerary auditor

Shipped on top of the Phase 2 rules. It is not a new agent and it does not re-curate the seed.

| Piece | Role |
| --- | --- |
| `src/travel_planner/audit.py` | Match pasted names, schedule the paste, price it, review it, rebuild from the open matches |
| `POST /api/planner/audits` | JSON verdict for the web page. No SSE and no LangGraph thread |
| `GET /api/planner/audits/example` | Sample that should fail: closed or reopening venue, invented names, Eid, crowds, a luxury stay, AED 900 |
| `/audit` | Plain-language verdict, recognized names, unknown names, problems, and the rebuilt days |

Exit check: `pytest tests/test_audit.py` passes offline. The sample verdict is `still_blocked`, Museum of the Future is absent from the rebuilt activities, and a paste with no catalog names does not grow a new trip.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Free-tier LLM rate limits | Slow or failed runs | Backoff, short prompts via pre-filtered shortlists, usage panel, deterministic fallbacks |
| Ollama Cloud auth or quota | Non-review nodes fall back to stubs | Require `OLLAMA_API_KEY` for `https://ollama.com`; keep deterministic fallbacks. Do not point Vercel at localhost |
| Small local models give bad structured output | Invalid local plans | Simple schemas, repair retry, deterministic node fallbacks |
| Curated data goes stale | Wrong closures or prices | `as_of` on every row, `operational_status` checks, visible staleness. Most catalog prices are already `estimated` |
| Station zones and restaurant cuisine are empty | Fares and food matching cannot use those fields | Planner-side area-to-zone map; restaurants match on area, `price_band`, and `meal_types` |
| Thin planning areas and satellite places | Empty days, or a family/mall interest with no hotel nearby | Merge Business Bay / Al Quoz / Creek with a Metro neighbour. Keep Dubailand, Al Barsha, and the other satellite places in the shortlist, and book the stay and meals in a planning area |
| Free API outages or quotas | Missing routes or places | Layered cache, API, local resolution, circuit breaker, `degraded` flag |
| Vercel stateless filesystem | Lost cache, checkpoints, or exports | Bundle static data read-only; use external storage for durable runtime state |
| Function timeout or cold start | Interrupted planner runs | Stream progress, cap revisions, keep dependencies lean, configure function duration where needed |
| Revision loop never converges | Cost and latency | `max_revisions` cap, finalize with warnings |
| Hallucinated venues | Untrustworthy output | LLM selects only from shortlisted IDs, validated against the DB. The auditor reports pasted names that are not in the catalog |
| Prompt injection via place text | Instruction hijack | Delimited data fields, no tool use driven by place text |

## Suggested Order of Work (Critical Path)

1. Phase 0 and 1 are done (models, seed, SQLite, holiday helpers).
2. Phase 2 and the Phase 3 graph skeleton, which prove the architecture without any LLM, on `data/dubai.sqlite`.
3. Phase 4 (LLM) in parallel with Phase 5 (adapters) and the Phase 6 Next.js UI/API shell.
4. Phase 7 as the final integration, Vercel preview, and evidence pass.
