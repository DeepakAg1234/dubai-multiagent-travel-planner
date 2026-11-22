# parse_request v1

Extract a Dubai trip from the request text in DATA.

Return JSON with these keys:
- days: integer 1-7, or null if the trip length is missing
- budget_aed: number, or null if no budget is stated
- travelers: integer, default 1
- interests: list of short interest words actually present (culture, food, beaches, family, nightlife, landmark, shopping, outdoor)
- hotel_tier: "budget", "mid", or "luxury", or null. "affordable" means budget. Never use "upscale" (that is a restaurant band).
- avoid_crowds: boolean
- pace: "relaxed", "balanced", or "packed"
- start_date: "YYYY-MM-DD" or null
- assumptions: list of short notes about what you inferred

The budget is the total for the group and includes accommodation. Flights are excluded. Do not invent a city other than Dubai.
