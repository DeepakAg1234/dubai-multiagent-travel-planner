# Data Research — Dubai AI Travel Planner

Every way this project can obtain data, how to use it, its limits, and how it fits the architecture in [architecture.md](./architecture.md). Product defaults are in [decisions.md](./decisions.md). What actually landed in `data/seed/` is [section 1.2](#12-delivered-catalog-2026-11).

> **Free-only policy:** This project uses only sources that are free and do not require a payment card. Paid APIs and card-gated services (such as the Google Maps Platform and paid LLM APIs) are deliberately excluded, and discontinued services (such as the Amadeus Self-Service hotel APIs) are not used.
>
> **Verification note (checked 2026-11-16):** Limits, fares, and ticket prices below were re-checked against provider pages and search results on this date. The list of sources is in [section 15](#15-verification-log). Re-check before committing, and record `source` and `as_of` for every value that enters the curated dataset. Items marked ⚠ could **not** be confirmed from an official page and are still indicative.

---

## 1. Summary

The table is the sourcing **strategy**. [Section 1.2](#12-delivered-catalog-2026-11) is what is in git.

| Need | Primary | Enrichment (free) | Fallback |
| --- | --- | --- | --- |
| Attractions | Curated dataset seeded from Visit Dubai, Wikidata, and Data.Dubai | OSM tags via Overpass (coordinates, category, `fee`, `opening_hours`) | Curated |
| Ticket price, closure, timed entry | Each attraction's official website | Visit Dubai listing, when the official page is missing a figure | Category price bands |
| Restaurants | Curated set seeded from Visit Dubai dining pages, filled by Overpass | OSM Overpass (`cuisine`, `opening_hours`, coordinates) | Curated |
| Hotels | Curated dataset. Identity and stars from Data.Dubai, Wikidata, and Overpass. Nightly ranges from each hotel's official site | none (no free live hotel API) | Curated |
| Routes and durations | OpenRouteService (free key) | OSRM public demo | Curated Metro/tram graph + straight-line estimates |
| Public transport fares | Curated RTA / Nol fare rules | none | Curated |
| Metro and tram ride times | RTA GTFS, when a free feed is published | Overpass Metro and tram route relations (station order) | Curated edges, then straight-line estimates |
| Costs (tickets, food) | Official attraction pages and curated price tables | Observed menus for a named restaurant | Category price bands |
| Weather | Open-Meteo (free, non-commercial) | Open-Meteo archive | Curated monthly climate |
| Request understanding | LLM (Ollama Cloud `nemotron-3-nano` for most nodes; Groq `openai/gpt-oss-20b` for `review`) | none | Rule-based defaults |

Strategy: **build the curated dataset first**, then layer the free APIs on top through repository interfaces. Every record keeps `source`, `as_of`, and a provenance class (`verified`, `api`, `estimated`).

The itinerary auditor reads this same catalog. A pasted name that is not in the seed is reported as unknown. The auditor does not call Wikidata, Nominatim, or a new place API to fill the gap.

### 1.1 Free sources and their limits

> Checked on 2026-11-16 (see [section 15](#15-verification-log)). Every source below is free and needs no payment card. Free limits can change without notice.

| Source | Account needed? | Verified limit / condition | Needed for MVP? |
| --- | --- | --- | --- |
| Curated local dataset (JSON / SQLite) | No | None. Costs only your time | **Yes** |
| Visit Dubai website | No | Manual reading and referencing | Yes (curation) |
| Wikidata Query Service | No | CC0. Polite use, identifying User-Agent, cache results. No key | Yes (curation only) |
| Data.Dubai / Dubai Pulse open datasets | Some APIs may need registration ⚠ | Per-dataset licence | Yes (curation), especially hotels and GTFS |
| Official attraction and hotel websites | No | Manual reading. Record facts and prices with a date. Do not copy long text or images | Yes (curation) |
| RTA fares, network info, and GTFS if published | No | Public pages. Confirm each feed's licence ⚠ | Yes (curation) |
| OpenStreetMap data | No | ODbL attribution, share-alike | Yes (curation extract) |
| Overpass API (public instance) | No | Guideline: about 10,000 requests/day and about 1 GB download/day | Yes (one-time extract; optional runtime enrichment) |
| Nominatim (public instance) | No | Max 1 request/second, identifying User-Agent, no bulk or autocomplete use | Curation only, missing coordinates |
| OSRM public demo server | No | Light use only ⚠ | Optional fallback |
| OpenRouteService (Standard plan) | Free API key | Directions 2,000/day, Matrix 500/day, Geocoding 3,000/day | Optional (Phase 5). No key is registered yet |
| Open-Meteo | No key | Non-commercial use only. 600/min, 5,000/hour, 10,000/day, 300,000/month | Optional live forecast; climate table is already in the seed |
| Ollama Cloud | Ollama account and `OLLAMA_API_KEY` | Default for every LLM node except `review`. Model `nemotron-3-nano` at `https://ollama.com`. Usage is billed from account credits | **Yes** for the deployed demo |
| Groq API | GroqCloud account and `GROQ_API_KEY` | **`review` uses `openai/gpt-oss-20b`.** The same model covers the other nodes when `LLM_PROVIDER=groq` | **Yes** for stage-2 review |
| Vercel Hobby / free deployment | Vercel account | Vercel Services (`web` + `planner-api`) preferred. Confirm current account, usage, and function limits before launch | **Yes** for deployment |
| Vercel-compatible external storage | Depends on provider | Needed only if `CACHE_STORE_URL` or `CHECKPOINT_STORE_URL` is set. No store is selected | Off for MVP |

**Bottom line:** the curated dataset is the foundation and is already committed. Live OpenRouteService, Overpass, and Open-Meteo are optional. The deployed demo uses Ollama Cloud (`nemotron-3-nano`) for most agents and Groq (`openai/gpt-oss-20b`) for `review`. A missing key leaves that node's Phase 3 stub in place. Wikidata and Nominatim are curation tools, not runtime dependencies. Durable cache and checkpoints stay off unless store URLs are set.

### 1.2 Delivered catalog (2026-11)

Phase 1 built `data/seed/` and compiles it to read-only SQLite. Later phases must not assume the original research targets were fully filled. Empty or estimated fields are planner constraints.

| File | Count | What is true in the files |
| --- | --- | --- |
| `places.json` | 81 | Eight `PLANNING_AREAS`. Interest floors met (culture 15, landmark 16, outdoor 33, mall 9, family 9, nightlife 6, free or cheap 57). `Museum of the Future` is `reopening` as of 2026-09-01. 13 timed-entry rows. Almost all prices `estimated`. Business Bay has 3 places, Al Quoz and Dubai Creek 5. |
| `restaurants.json` | 80 | 10 per area, lunch + dinner, all `estimated`. `cuisine` is `unspecified`. No menu `price_aed`. |
| `hotels.json` | 32 | Every area has budget, mid, and luxury. Nightly peak/summer ranges are shared tier bands from section 5.1, not hotel-site quotes. `stars` is empty. 24 have `metro_nearby`. Cheapest budget night: AED 170 peak / AED 120 summer. |
| `transit_stations.json` | 64 | Red 33, Green 18, Tram 11, Union and Burjuman `Red,Green`. `zone` is empty. Station order came from Wikipedia line tables, not GTFS. |
| `transit_edges.json` | 65 | Estimated hop minutes, plus 6-minute walks JLT↔DMCC and Marina↔Sobha Realty. |
| `fares.json` | 20 | Verified Silver 3 / 5 / 7.50, Gold double, Red Ticket 4 / 6 / 8.50, Silver 7-day 50 / 80 / 110. Estimated: 1-day pass AED 20, taxi flag/km/minimum, Abra AED 1. No bus table. |
| `price_bands.json` | 10 | Food budget 25–45, mid 70–140, upscale 180–400, plus coffee, water, activity, typical taxi. All `estimated`. |
| `climate.json` | 12 | Open-Meteo archive 2016-01-01 to 2025-12-31 at 25.2048, 55.2708. July mean high 41.0 °C, low 30.7 °C. Climatology, not a forecast. |
| `holidays.json` | 14 | 2026–2027. Ramadan `drop_lunch`. Eid `heritage_may_close_first_day` + `high_crowd`. National Day `high_crowd`. Islamic dates `estimated` until a FAHR circular. |

Curation that was **not** completed, so do not code as if it was: official-site ticket quotes for most attractions, hotel website nightly rates, Overpass `cuisine` and hotel `stars`, RTA GTFS, station Nol zones.

The original sizing targets (80–120 places, 80–120 restaurants, 30–40 hotels) were a floor for a usable itinerary. They are met. Re-curation is out of scope for Phases 2–7.

---

## 2. Method 1 — Curated Local Dataset (foundation)

**What:** Hand-built JSON seed files compiled to SQLite. Source of truth for demos and the offline fallback.

**Contents and sizing**

| Dataset | Target size | Key fields | Requisite sources |
| --- | --- | --- | --- |
| Places (attractions, beaches, cultural sites, markets) | 80 to 120, with a floor in each interest bucket | name, area, lat/lng, tags, price range, crowd level, visit minutes, hours, indoor flag, timed-entry flag, operational status | Visit Dubai and Wikidata for the named list and official URL. Overpass for coordinates, category, `fee`, and hours. The attraction's own site for price, closure, and timed entry |
| Restaurants (local food, various price tiers) | 80 to 120, about 6 to 8 in each planning area, across budget, mid, and upscale | name, cuisine, area, lat/lng, price band, meal types, hours | Visit Dubai dining pages for the named shortlist. Overpass to fill area, cuisine, coordinates, and hours. Price tier is `estimated` unless a menu price is recorded |
| Hotels | 30 to 40: two per major area for each supported tier | area, tier, nightly range by season, lat/lng, Metro proximity | Data.Dubai, Wikidata, and Overpass for name, coordinates, and stars. Each hotel's official site for the nightly range. Metro proximity is computed from the station table |
| Transit stations | Metro Red/Green lines, Tram, key Bus hubs, Water taxi/Abra stops | line, zone, lat/lng | RTA open data, or Overpass `railway=station` |
| Transit edges | A ride time on every Metro and tram segment used for sequencing | from, to, minutes | RTA GTFS when published. Otherwise Overpass route relations for station order, with estimated minutes |
| Fares | Zone-based Nol rules, passes, taxi flag fall and per-km | amount, card type | RTA fare pages |
| Price bands | Meals by tier, coffee, water, taxi typical trip | min/max AED | Observed menus and RTA taxi tariffs. These bands price unnamed meals |
| Climate | 12 months | high/low, rain, humidity | Open-Meteo archive, checked once and stored |
| Holidays | 10 to 24 city-wide rows for the next year or two | kind, start, end, effects | UAE government list and FAHR circulars for fixed dates; expected Hijri dates `estimated` |

Place floors, which may overlap: culture and heritage 15–20, landmarks and viewpoints 10–15, beaches and outdoor 10–15, shopping and malls 8–10, family 8–10, nightlife 6–8, and free or very cheap 15–20. Every planning area (Old Dubai, Downtown, Marina / JBR, Jumeirah, Al Quoz, Palm, Dubai Creek, Business Bay) should contain places, meals, and at least one hotel per supported tier.

**How to build it**

1. Pick areas that cover the demo requests: Old Dubai (Al Fahidi, Deira, Bur Dubai), Downtown, Dubai Marina / JBR, Jumeirah, Al Quoz, Palm, Dubai Creek, Business Bay.
2. Build the named place list from Visit Dubai and Wikidata (category, coordinates, official URL). Build the named restaurant shortlist from Visit Dubai dining and neighborhood pages.
3. Run a one-time Overpass extract per area to fill restaurants and missing place coordinates, plus `cuisine`, `opening_hours`, `fee`, and hotel `stars`. Cache the response. Do not use the public Overpass instance as the app's backend.
4. For each place that can appear in a plan, pull price, closure, and timed-entry from the attraction's own site. For each hotel, pull a peak and a summer nightly range from the hotel's own site.
5. Use Nominatim only to fill a coordinate that Wikidata and Overpass both missed, one request at a time, inside its usage policy.
6. Tag with interests (`culture`, `food`, `beach`, `family`, `shopping`, `nightlife`, `outdoor`) and a subjective `crowd_level` with a rule (for example, high for Burj Khalifa observation deck at sunset and Dubai Mall on weekends). Crowd level stays `estimated`. Wikidata visitor counts, when present, can inform that rubric.
7. Record `source` URL and `as_of` date on every row.
8. Validate with Pydantic at build time. Fail the build on missing coordinates or prices.

**Status:** this method was used. The committed files and remaining gaps are in [section 1.2](#12-delivered-catalog-2026-11). Coordinates were filled mainly with Nominatim. Cuisine, stars, GTFS, and most official-site prices were not filled.

**Cost:** 💚 **Free.** The real cost is curation time, roughly 1 to 2 days for the MVP-sized dataset.

**Pros:** Deterministic, free, offline, auditable. **Cons:** Manual upkeep, can go stale. Mitigated by `as_of` and a staleness warning in the UI for rows older than a threshold.

**Provenance class:** `verified` when copied from an official page, `estimated` for ranges and crowd levels.

---

## 3. Method 2 — Official Tourism and Open Data

### 3.1 Visit Dubai (visitdubai.com)

- **Use:** Named attractions by category, dining and neighborhood guides, and the restaurant shortlist. Descriptions, event listings, and neighborhood guides. This is the quality list. Overpass fills the count.
- **Access:** Public website. No documented public API for general use ⚠.
- **Approach:** Manual curation into the seed dataset. For this project, prefer manual extraction of a small set. If scraping were ever considered, review the site's terms and robots.txt first.
- **Limits:** Marketing language, uneven price info, no structured coordinates.
- **Cost:** 💚 **Free** to read and reference.

### 3.2 Data.Dubai / Dubai Pulse (data.dubai, dubaipulse.gov.ae)

- **Use:** Open government datasets. The sets this catalog depends on are hotel establishments (name, location, star rating, usually without current rates), tourist attractions or landmarks, and public transport (RTA) datasets, including a GTFS feed if one is published. Tourism statistics and points of interest are optional.
- **Access:** Open data portal, many datasets downloadable as CSV or JSON. Some Dubai Pulse APIs may require registration or approval ⚠. Only use downloads and APIs that are free and need no card.
- **Approach:** Search the portal for tourism, hospitality, and transport datasets. Download, filter to the demo areas, normalize into the local schema. Check each dataset's licence.
- **Limits:** Dataset availability and freshness vary. Field names and languages (English/Arabic) differ. Hotel datasets may list establishments without current rates.
- **Cost:** 💚 **Free.** Open data is free to download. A few datasets may carry licence conditions rather than fees ⚠.

### 3.3 Dubai RTA (rta.ae)

- **Use:** Fare tables (Nol card zones, single tickets, passes), Metro/Tram/Bus network, operating hours, Abra and water taxi fares, taxi tariffs.
- **Access:** Public website and RTA open data. GTFS-style feeds may exist through the open data portal ⚠.
- **Approach:** Manually encode the fare rules (7 zones, fare by number of zones crossed) into the `fares` table. Prefer an RTA GTFS feed for `transit_stations` and `transit_edges`. No free GTFS feed was used. Station order was taken from Wikipedia Red/Green/Tram tables; hop minutes are `estimated`. `zone` was left empty, so the fare calculator uses a planner-side area-to-zone map.
- **Verified values (RTA nol fares page and recent RTA-sourced guides, 2026-11-16):**

  | Item | Value |
  | --- | --- |
  | Zones | Dubai is split into 7 zones |
  | Silver card, per trip | AED 3 (1 zone), AED 5 (2 adjacent zones), AED 7.50 (more than 2 zones) |
  | Gold card, per trip | AED 6 / 10 / 15 (double the Silver fare) |
  | Red Ticket, per trip | AED 4 / 6 / 8.50 |
  | Silver card price | AED 25, of which AED 19 is credit |
  | Red Ticket price | AED 2 (no credit; load trips) ⚠ third-party figure |
  | Transfers | Metro, tram, and bus changes within 30 minutes count as one journey |
  | 7-day pass (Silver) | AED 50 (1 zone), AED 80 (2 zones), AED 110 (all zones) |
  | 1-day Travel Pass (Regular) | About AED 20 on a Red Ticket ⚠ price not on the RTA fare table, from a third-party guide. Confirm with RTA |
  | Taxi, street hail | Flag fall AED 5 (06:00 to 22:00) or AED 5.50 (night), AED 2.45 per km (Dubai Taxi), minimum AED 12 ⚠ |
  | Taxi, booked by app | Base AED 5, booking fee AED 4 to 7.50 by time of day, about AED 1.97 per km (RTA, since Nov 2025), minimum AED 13 ⚠ the two sources differ |
  | Taxi from the airport | From about AED 20 to 25 |

- **Important correction:** RTA's current fare page does **not** publish an automatic daily spending cap for Silver cards. Older guides mention a roughly AED 14 per day cap, which should not be used. The only way to cap a day is to buy a 1-day Travel Pass or a 7-day pass, so the budget agent should compare pay-per-trip against the passes instead of assuming a cap.
- **Provenance class:** `verified` once confirmed from RTA.
- **Cost:** 💚 **Free** to read and encode. (These are what *travelers* pay, which makes them budget inputs, not costs of accessing the data.)

### 3.4 Public holidays (UAE portal and FAHR)

- **Use:** City-wide calendar for Ramadan, Eid, and fixed public holidays. Effects are category rules, not a per-place closure list.
- **Access:** UAE Government public-holiday pages; FAHR circulars when issued. Islamic dates from secondary calendars stay `estimated` until a moon-sighting announcement.
- **In the seed:** `holidays.json`, 14 rows for 2026–2027. Applied in `rules/holidays.py`.
- **Cost:** 💚 **Free.**

---

## 4. Method 3 — OpenStreetMap Ecosystem and Free Routing

### 4.1 Overpass API

- **Endpoint:** `https://overpass-api.de/api/interpreter` (public instance, shared and rate-limited, so use sparingly and cache).
- **Use:** Discover restaurants, cafes, museums, beaches, viewpoints, and metro stations with coordinates and tags.
- **Example query (Dubai area bounding box, restaurants):**

```
[out:json][timeout:25];
(
  node["amenity"="restaurant"](25.05,55.10,25.30,55.40);
  way["amenity"="restaurant"](25.05,55.10,25.30,55.40);
);
out center tags;
```

- **Useful tags:** `amenity=restaurant|cafe`, `tourism=museum|attraction|viewpoint|hotel`, `natural=beach`, `shop=mall`, `leisure=park`, `railway=station` with `station=subway`, `cuisine=*`, `opening_hours=*`, `fee=*`, `stars=*`, `outdoor_seating=*`. Query once per planning area and keep named features. `fee=no` seeds the free-place floor. `stars` seeds hotel tier. Neither tag is a price.
- **Limits:** Inconsistent tagging, no prices, uneven opening hours. Good for discovery, weak for quality ranking.
- **Licence:** ODbL, so attribution is required and share-alike applies to derived databases ⚠ (consider before redistributing a derived dataset).
- **Cost:** 💚 **Free.**
- **Verified usage guidance (Overpass docs):** expect to send at most about 10,000 requests per day and keep downloads under about 1 GB per day. The server may return HTTP 429 (rate limit) or 504 (resource limit). Set `[timeout:...]` and `[maxsize:...]` explicitly, because small requests are prioritised. The docs say that relying on the public instance as the backend of an app aimed at more than OSM mappers is problematic, so treat it as an enrichment source, cache results, and keep the curated restaurants as the fallback.
- **Provenance class:** `api`.

### 4.2 Nominatim (geocoding)

- **Use:** Fill a missing coordinate while curating the seed dataset, only after Wikidata and Overpass have no point for that place. Not for discovery, bulk geocoding, or runtime use.
- **Cost:** 💚 **Free** within the usage policy.
- **Verified policy (OSMF Nominatim usage policy):** absolute maximum of 1 request per second; send a valid HTTP Referer or an identifying User-Agent (default library User-Agents are not accepted); display attribution; cache results. Forbidden: autocomplete search, systematic grid or "download all POIs" queries, scraping the details page, and reselling results. The policy also says the public API must not be built into no-code or auto-generated tools as a generic geocoder, so use it only as a deliberate, one-off curation aid. Periodic runtime requests count as bulk geocoding and are strongly discouraged.

### 4.3 Wikidata (curation only)

- **Endpoint:** `https://query.wikidata.org/sparql`. No API key. Data is CC0.
- **Use:** Landmarks, museums, beaches, and hotels that have a Wikidata item: coordinates, instance-of category, official website, and located-in area. Visitor counts, when the item has them, can inform the crowd rubric and stay `estimated`. Thin for ordinary restaurants, so it does not replace Overpass there.
- **Approach:** A small set of SPARQL queries, one per category, saved with the seed build. Send an identifying User-Agent, cache the JSON, and check the result into `data/seed/`. The planner never calls Wikidata at runtime.
- **Limits:** Coverage is uneven. Many Dubai restaurants and smaller hotels have no item. Star ratings and ticket prices are often missing. Do not treat a missing Wikidata item as evidence that the place does not exist.
- **Licence:** CC0, so attribution is not required. Still store `source` as the Wikidata item URL so a row can be re-checked.
- **Cost:** 💚 **Free.**
- **Provenance class:** `verified` for name, coordinates, and official URL copied from the item. `estimated` for any crowd hint derived from a visitor count.
- **Not re-checked against the live endpoint on 2026-11-16.** Confirm the query and the User-Agent policy before the first extract ⚠.

### 4.4 OpenRouteService (primary routing) and OSRM (fallback)

- **OpenRouteService (ORS):** Free Standard plan with an API key (account sign-up, no payment card). Supports driving, walking, and matrix requests.
  - Typical endpoints (confirm in the ORS docs when writing the adapter ⚠): `POST https://api.openrouteservice.org/v2/directions/{profile}` and `POST https://api.openrouteservice.org/v2/matrix/{profile}`, with profiles such as `driving-car` and `foot-walking`. The key is sent in the `Authorization` header.
  - **Verified limits (ORS plans page), daily / per minute:** Directions 2,000 / 40, Matrix 500 / 40, Isochrones 500 / 20, Geocoding 3,000 / 100, POIs 500 / 60.
  - A **Collaborative** plan with higher limits (Directions 10,000/day, Matrix 2,500/day) is available to humanitarian, academic, governmental, and not-for-profit projects, so a course project may qualify. An **On-Premise** option has no limits but needs your own server, so it is not used here.
  - **Capacity check:** one itinerary needs about 4 matrix calls (one per day of a 4-day trip), so the 500 per day Standard Matrix limit covers roughly 125 uncached plans per day. That is plenty for a demo. Throttle to stay under 40 calls per minute.
- **OSRM public demo server (fallback):** `https://router.project-osrm.org/route/v1/{driving|walking}/lon,lat;lon,lat`. Free, no key, intended for light use, and mainly driving and walking profiles ⚠.
- **Limits of both:** No Dubai Metro, tram, or bus awareness, so public transport legs and fares come from the curated transit graph and RTA fare table. Road durations are estimates and do not include live traffic.
- **Fallback order:** ORS, then OSRM, then the curated Metro/tram graph plus straight-line distance estimates marked `estimated`.
- **Cost:** 💚 **Free.**
- **Provenance class:** `api` for road durations and distances, `estimated` for the curated-graph fallback.

---

## 5. Method 4 — Accommodation Data

There is no free live hotel API in this project. The Amadeus Self-Service hotel APIs were discontinued on 2026-07-17, and the other hotel-data options are paid or approval-gated, so they are out of scope. Hotels come from the curated dataset only.

### 5.1 Curated hotel dataset

- **Identity and tier:** Data.Dubai hotel establishments, Wikidata, and Overpass `tourism=hotel` with `stars`. Use these to close gaps so each planning area has a budget, mid, and luxury option. Star rating maps onto tier. These sources usually have no current nightly rate.
- **Nightly range:** intended source is the hotel's own website. The seed instead stores shared peak and summer bands from the tier mapping below, nudged per row, all `estimated`. There is still no free live hotel rate API.
- **Metro proximity:** computed from the curated station table (`metro_nearby` on 24 of 32 hotels).
- Season is not a hotel-table column. `Hotel.stay_option("peak" | "summer")` picks the range. Summer is May–September.
- Tier mapping used in the seed (indicative ⚠): budget (about AED 150 to 350), mid (about AED 350 to 700), luxury (AED 700+).
- **Stars:** intended from Data.Dubai / Overpass. The seed left `stars` empty; tier is the field that matters.
- **Provenance class:** `estimated` for identity geocodes and nightly ranges in the current seed.
- **Cost:** 💚 **Free** to build. The nightly rates it contains are inputs to the traveler's budget, not data fees.

---

## 6. Method 5 — Cost Data (Activities, Food, Transport)

| Cost | Source | Method |
| --- | --- | --- |
| Attraction tickets | The attraction's official website. Visit Dubai only when the official page has no figure | Record adult price, child price, timed-entry flag, and "as of" date. Prices vary by time slot and package, so store a range and a default. |
| Meals | Curated price bands by tier, from observed menus | Budget local meal, mid-range, upscale. Add drinks and tip assumptions. |
| Metro, tram, bus | RTA fare tables (see 3.3) | Zone rule in code. No automatic daily cap on Silver cards, so compare pay-per-trip against the 1-day and 7-day passes. |
| Taxi | RTA / Dubai Taxi tariff (see 3.3) | Flag fall + per-km × distance, then apply the minimum fare, booking fee for app rides, and airport surcharge. The sources differ on the per-km rate, so budget with the higher one (AED 2.45) and mark it `estimated`. |
| Abra / water taxi | RTA fare page ⚠ | Fixed small fare, curated. |
| Buffer | Rule | Default 10% contingency. |

**Cost of obtaining this data:** 💚 **Free.** Official pages are public. The prices listed here are what travelers pay and feed the budget calculation.

**Attraction prices (checked 2026-11-16):**

| Attraction | Adult price | Child price | Status / source |
| --- | --- | --- | --- |
| Dubai Frame | AED 50 | AED 20 (ages 3 to 12), under 3 free | Official site (dubaiframe.ae). Visit Dubai's experience listing shows AED 52.50 / 21.00, which looks like a booking-fee-inclusive price |
| Burj Khalifa, At the Top (levels 124 and 125) | AED 189 | Not checked | Price reported by a ticket comparison site as the official price. Varies by date and time slot ⚠ |
| Sky Views Dubai | AED 89 | Not checked | Comparison site ⚠ |
| The View at The Palm | AED 115 official (resellers from AED 89) | Not checked | Comparison site ⚠ |
| Ain Dubai (Views, shared cabin) | From AED 145 | Not checked | Comparison site ⚠ |
| **Museum of the Future** | Last price AED 169 | Under 4 free | ⚠ **Closed since early September 2026 for an overhaul. Expected to reopen in Q1 2027, no date set, no tickets on sale.** Do not include it in itineraries until it reopens. The review agent should flag it |
| Al Fahidi / Bastakiya, Gold and Spice Souks | Free | Free | General knowledge, not rechecked ⚠ |
| Jumeirah public beaches, Kite Beach | Free | Free | General knowledge, not rechecked ⚠ |
| Abra crossing | About AED 1 | n/a | General knowledge, not rechecked ⚠ |

Lesson for the dataset: add an `operational_status` field (`open`, `closed`, `reopening`) with a `status_as_of` date to every place, and make the review agent reject closed places. Museum of the Future is a real example of a flagship attraction that disappears from a plan.

---

## 7. Method 6 — Weather and Climate

### 7.1 Open-Meteo (free, no API key, non-commercial use)

- **Forecast:** `GET https://api.open-meteo.com/v1/forecast?latitude=25.2048&longitude=55.2708&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,uv_index_max&timezone=Asia/Dubai`
- **Horizon:** Typically up to about 16 days ahead.
- **Historical / climate:** `https://archive-api.open-meteo.com/v1/archive` for past dates, useful to build monthly averages for trips further out. Precompute once and store in the curated climate table instead of calling it at runtime.
- **Use:** Flag extreme heat (midday outdoor avoidance in summer), rain risk, UV; prefer indoor activities on hot afternoons.
- **Fallback:** Curated monthly climate table in `climate.json` (January mean high 24.0 °C, July 41.0 °C, from the 2016–2025 archive).
- **Provenance class:** `api` for forecast, `estimated` for climatology.
- **Cost:** 💚 **Free** for non-commercial use, no API key. **Verified free-tier limits:** 600 calls/minute, 5,000/hour, 10,000/day, 300,000/month, no uptime guarantee. A prototype or demo stays far inside these, especially with the 3-hour cache.
- **Condition:** The free API is for **non-commercial use only**. This project is an educational demo, which fits. If it were ever commercialized, a paid plan would be required, so that would need a different weather source.
- **How a call is counted:** requests with more than 10 variables or more than 2 weeks of data count as fractional multiple calls. A daily forecast with a handful of variables is 1 call.
- **Attribution:** data is CC BY 4.0, so credit Open-Meteo.

---

## 8. Method 7 — LLM as a Data Source (restricted use)

The LLM is **not** a source of facts such as prices, hours, or coordinates. It is used for:

| Use | Allowed | Guardrail |
| --- | --- | --- |
| Parsing the request into constraints | Yes | Pydantic validation, defaults recorded as assumptions |
| Ranking and selecting among provided candidates | Yes | Must return IDs from the candidate list |
| Writing descriptions and day themes | Yes | Descriptions drawn from stored facts |
| Estimating a missing price | Only as last resort | Marked `estimated`, flagged for curation |
| Inventing places or prices | No | Output validated against known IDs |

Optional offline use of an LLM during curation: draft seed rows from official text, then a human verifies. Never ship unverified LLM-generated facts as `verified`.

### 8.1 Free LLM options

The project only uses free LLM options. The model is a configurable setting, so the agents do not depend on a specific one.

| Option | Cost | Conditions |
| --- | --- | --- |
| **Ollama Cloud** (default `nemotron-3-nano` at `https://ollama.com`) | Usage billed from Ollama account credits | Used for every LLM node except `review`. Authenticate with `Authorization: Bearer <OLLAMA_API_KEY>`. Do not send personal data |
| **Groq API** (`openai/gpt-oss-20b`) | Free developer limits ⚠ confirm current console.groq.com rates | **`review` always.** Also used for the other nodes when `LLM_PROVIDER=groq`. Do not send personal data |

Notes:

- Free tiers and model names change quickly. Keep the provider and model in configuration and re-check before a demo.
- Each itinerary run makes about 6 to 10 LLM calls (parse, plan, research, logistics, review, finalize, plus revisions) of roughly 2,000 to 6,000 tokens each, so about 20,000 to 60,000 tokens per run. A revision loop adds a few more calls. Track calls per run in the UI so the demo stays inside the free rate limits.
- Reduce load by using short candidate shortlists, caching identical requests, and keeping budget and review logic in deterministic code rather than the LLM.

---

## 9. Method 8 — User-Provided and Derived Data

- **User input:** budget, days, interests, hotel tier, crowd preference, dates, group size.
- **Derived:** pace limits, meal slots, per-day cost caps, crowd windows (for example, early mornings and weekday afternoons are generally quieter ⚠ validate per attraction), heat windows.
- **Session data:** previous plan versions in the revision loop are retained in state for the "what changed" view.

---

## 9.1 Vercel Runtime and Hosting Research

The deployment target is Vercel, so the application should be shaped around web-native services rather than Streamlit.

**Recommended deployment shape**

| Component | Vercel-native choice | Notes |
| --- | --- | --- |
| Frontend | Next.js / React | Renders form inputs, live agent timeline, graph view, budget charts, exports |
| Planner backend | Python FastAPI on Vercel Functions or Vercel Services | Runs LangGraph and streams `AgentEvent` updates to the browser |
| Streaming | Server-Sent Events over HTTP | Fits one-way progress updates from planner to UI |
| Static data | Bundled JSON or read-only SQLite | Good for curated seed data; generated DB should be built before deploy or during build |
| Runtime cache | Vercel-compatible external store | Use for route/weather cache, API quota counters, and repeated requests |
| Checkpoints | External store | Required for durable LangGraph interrupt/resume across page refreshes or separate requests |

**Vercel constraints that affect design**

- Functions are stateless and can scale to zero. Do not rely on local filesystem writes for cache, checkpoints, exports, or generated databases.
- Python is supported for serverless functions, but dependency size and cold start time should be monitored. If the Python bundle becomes too large, consider trimming dependencies first, then a Vercel container image.
- Long planner runs should stream progress instead of staying silent until the end. Keep the MVP run comfortably within function duration limits.
- The deployed app uses Ollama Cloud (`nemotron-3-nano`) for most nodes and Groq (`openai/gpt-oss-20b`) for `review`. A missing `OLLAMA_API_KEY` or `GROQ_API_KEY` keeps that provider's Phase 3 stubs. Do not point Vercel at a localhost Ollama server.
- Store secrets as Vercel environment variables, with `.env.example` documenting the names only.

**Storage candidates to evaluate**

| Need | Candidate | Why |
| --- | --- | --- |
| Cache and quota counters | Upstash Redis or Vercel Runtime Cache | Simple key-value access and TTLs |
| Durable checkpoints / run records | Neon Postgres, Turso, or Upstash Redis | Needed for resume, history, and cross-request state |
| Export files | Vercel Blob, or generate on demand | Avoid local file writes in deployed functions |

For the MVP, keep runs synchronous and stream-only, use bundled curated data, and leave cache and checkpoints off unless `CACHE_STORE_URL` / `CHECKPOINT_STORE_URL` are set. No Marketplace store is selected ([decisions.md](./decisions.md)). Map view is post-MVP.

---

## 10. Provenance Model

| Class | Meaning | Examples | UI badge |
| --- | --- | --- | --- |
| `verified` | Checked against an official or authoritative source, with date | RTA fares, official ticket price, attraction coordinates | ✅ |
| `api` | Returned by a live free API for this request | ORS route duration, Overpass place tags, Open-Meteo forecast | 🌐 |
| `estimated` | Derived, banded, or modeled | Hotel nightly range, meal cost, crowd level, climatology | ≈ |

Rules: every cost line and every travel leg carries a class. If a value is blended (API duration plus estimated cost), the weaker class applies. Totals report how much of the budget is verified vs. estimated.

---

## 11. Fallback and Degradation Matrix

| Failure | Behavior | UI signal |
| --- | --- | --- |
| No ORS key or ORS daily limit reached | Use OSRM, then the curated graph | "Using fallback routing" notice |
| OSRM unavailable | Use curated Metro/tram graph and straight-line estimates | Degraded badge, durations marked estimated |
| Overpass rate-limited (HTTP 429 / 504) | Use curated restaurants | Degraded badge |
| Open-Meteo down or rate-limited | Use climate table | "Climatology, not forecast" |
| LLM rate limit or quota hit | Retry with backoff, then a deterministic path for that node | Warning with the node name |
| No live hotel source (always) | Curated hotels only | Hotel prices marked estimated |
| Place flagged closed (for example Museum of the Future) | Exclude from plan, suggest an alternative | Warning with status date |
| All APIs off | Fully local run | "Offline mode" banner |

Caching reduces repeat calls when a store is configured: places 30 days, routes 7 days, weather 3 hours. MVP has no `CACHE_STORE_URL`.

---

## 12. Legal, Licensing, and Ethics Checklist

- **OpenStreetMap:** ODbL attribution ("© OpenStreetMap contributors") and share-alike for derived databases.
- **Wikidata:** CC0. No attribution required. Store the item URL as `source`. Send an identifying User-Agent and cache curation queries.
- **Open-Meteo:** CC BY 4.0 attribution, and non-commercial use only on the free API.
- **OpenRouteService:** Follow the plan terms. Credit the service, and respect the daily and per-minute limits.
- **Data.Dubai / Dubai Pulse:** Check each dataset's licence and attribution requirements.
- **Visit Dubai and attraction sites:** Facts and prices can be referenced with source and date. Do not copy long marketing text or images. Avoid scraping without permission.
- **Public APIs (Nominatim, Overpass, OSRM demo):** Respect usage policies, identify the application, throttle, and cache.
- **LLM free tiers:** Do not send personal data, because free-tier data may be used for model improvement.
- **Keys:** Keep ORS and LLM keys in `.env`, out of version control.
- **Disclaimer in UI:** Costs are estimates, not quotes. Verify prices and opening hours before travel.

### 12.1 Running cost

Running the project costs **$0** and needs no card.

| Component | Choice | Limit to remember |
| --- | --- | --- |
| Data | Curated dataset | None |
| Places and restaurants | Visit Dubai, Wikidata, Overpass extract | Overpass about 10,000 requests/day guideline. Wikidata is curation-only |
| Routing | OpenRouteService free, OSRM fallback | ORS Matrix 500/day, Directions 2,000/day, 40/min |
| Weather | Open-Meteo free | 10,000 calls/day, non-commercial only |
| LLM | Ollama Cloud `nemotron-3-nano` (most nodes) + Groq `openai/gpt-oss-20b` (`review`) | Ollama usage is billed. Do not send personal data |
| Hosting | Vercel Services (`web` + `planner-api`) | Confirm current free-tier limits before launch; functions are stateless and have duration/bundle limits |
| Runtime persistence | Off unless store URLs are set | No provider chosen yet |

Free hosting and serverless functions may have cold starts or scale-to-zero behavior, so open the app and run one warm-up scenario before a live demo.

---

## 13. Recommended Build Order for Data

1. **Seed dataset** — **done.** Places, restaurants, hotels, transit, fares, price bands, climate, holidays. See [section 1.2](#12-delivered-catalog-2026-11). Do not block later phases on filling cuisine, stars, GTFS, or official-site prices.
2. **Open-Meteo adapter** (free, no key, low risk). Climate table already exists as the fallback.
3. **OpenRouteService adapter** for durations, with an OSRM/curated-graph fallback. Register a Standard-plan key first. Offline graph already works.
4. **Overpass adapter** for optional runtime restaurant and place enrichment (cuisine, hours). Must not overwrite prices, `operational_status`, or hotel nightly ranges.

---

## 14. Open Research Tasks

Checked off items are reflected in the seed or in [decisions.md](./decisions.md). Remaining items do **not** block Phases 2–4.

- [ ] List Data.Dubai / Dubai Pulse datasets that are relevant, with licence and format. Confirm the hotel-establishment file has name, location, and star rating.
- [x] Confirm whether a usable RTA GTFS feed is available for Metro and tram segment times. **No GTFS was used.** Wikipedia station order + estimated minutes are in the seed.
- [ ] Confirm a Wikidata SPARQL query for Dubai landmarks, museums, and hotels, and the Query Service User-Agent policy.
- [x] Confirm current Nol zones and per-trip fares from RTA (done 2026-11-16, see 3.3). Encoded in `fares.json`.
- [ ] Confirm the 1-day Travel Pass price and the taxi per-km rate directly with RTA (sources disagree). Seed keeps those rows `estimated`.
- [ ] Create an OpenRouteService free key and confirm the endpoints, profiles, and matrix size limits. **Not registered in Phase 0.** Offline graph is enough until Phase 5.
- [ ] Confirm Groq and Gemini free-tier rate limits and whether either signup needs a billing card. If a card is required, keep that provider's Phase 3 stubs on Vercel.
- [ ] Confirm current Vercel Hobby/free limits for Python functions, Vercel Services, function duration, and bundle size.
- [x] Choose the deployed cache/checkpoint store, or explicitly defer durable resume for MVP. **Deferred.** Cache and checkpoints off unless store URLs are set. No Marketplace store selected.
- [ ] Test a local Ollama model for reliable structured JSON output on the agent schemas.
- [ ] Decide whether to apply for the OpenRouteService Collaborative plan (academic or non-profit) for higher quotas.
- [x] Add `operational_status` to places. Museum of the Future is `reopening` as of 2026-09-01, last listed ticket AED 169. Reopening date still unset.
- [ ] Confirm official Burj Khalifa and other attraction prices on their own sites (current seed values are mostly estimated).
- [x] Seasonal hotel ranges: peak vs summer columns on each hotel, May–September = summer. Not a separate multiplier table. Ranges are still estimated tier bands.
- [ ] Collect current official ticket prices for the top 20 attractions.
- [x] Crowd-level field is on every place (`low` / `medium` / `high`) as `estimated`.
- [x] Holiday calendar 2026–2027 in `holidays.json` (UAE portal + FAHR for some Eid/National Day rows; Hijri dates estimated).
- [ ] Re-verify all limits before launch (this file is a 2026-11-16 snapshot; catalog as_of dates are 2026-11-17 and 2026-11-18).

---

## 15. Verification Log

What was checked on **2026-11-16**, and how reliable each check is.

| Topic | Source | Reliability |
| --- | --- | --- |
| Open-Meteo free limits, non-commercial condition, call counting | open-meteo.com/en/pricing, fetched directly | **High** (official) |
| OpenRouteService limits and plans | openrouteservice.org/plans, fetched directly | **High** (official) |
| ORS endpoint paths and profiles | General knowledge, not checked this session | **Low** ⚠ confirm in ORS docs |
| Nominatim usage policy | operations.osmfoundation.org/policies/nominatim, fetched directly | **High** (official) |
| Overpass usage guidance | dev.overpass-api.de/overpass-doc (commons page), fetched directly | **High** (official) |
| Gemini free tier exists, data used to improve products | Google AI Studio pricing page via search results (the direct fetch timed out) | **Medium to high** |
| Gemini free-tier rate limits, and whether a card is needed | Not checked | **Unknown** ⚠ |
| Vercel Functions support Python, streaming, stateless execution, and function limits | Vercel platform docs / deployment guidance | **Medium** (confirm against current docs before launch) |
| RTA nol zones, per-trip fares, 7-day passes | rta.ae nol fares page, via search results | **High** (official page) |
| 1-day pass, Silver card price, taxi tariffs | Third-party guides citing RTA and Dubai Taxi. Sources disagree on the taxi per-km rate | **Medium** |
| Dubai Frame prices | dubaiframe.ae, via search results | **High** (official) |
| Burj Khalifa and other observation decks | Ticket comparison site | **Medium** |
| Museum of the Future closure | Time Out / tbreak report citing the museum FAQ | **Medium to high** |
| Streamlit Community Cloud limits | No longer primary deployment target after Vercel-native revision | **Not applicable** |

Not re-checked: Visit Dubai and Data.Dubai availability or licences, hotel nightly rates, restaurant prices, free-attraction claims, Overpass and OSRM availability, and the Wikidata Query Service. Wikidata is included as a free CC0 curation source. Confirm the endpoint and a sample query before the first extract.
