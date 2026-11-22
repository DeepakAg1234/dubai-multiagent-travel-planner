# orchestrator_plan v1

Turn the constraints in DATA into a plan brief.

Return JSON:
- days: list of {day, theme, areas, crowd_hints}. One entry per trip day, day numbers starting at 1.
- cuisine_focus: [] or ["local"]. Do not name a restaurant cuisine.
- notes: short list of planning notes

areas must be taken from the allowed_areas list in DATA. A day may name a satellite area only when a shortlisted place would live there. Hotel and meal areas stay inside the eight planning areas. Prefer low-crowd indoor themes when avoid_crowds is true or the day is a high-crowd holiday.
