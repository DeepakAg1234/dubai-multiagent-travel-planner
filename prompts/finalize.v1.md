# finalize v1

Write the traveler-facing narrative for the itinerary in DATA.

Return JSON:
- narrative: a short paragraph. Mention holiday notes when DATA includes them. Mention assumptions and warnings briefly.
- provenance_notes: list of short sentences. You must call out that place, hotel, restaurant, fare-estimate, and climate figures are estimated, that Dubai Frame's adult ticket is the only verified place price, and the station provenance counts given in DATA.

Do not invent venues or prices that are not in DATA.
