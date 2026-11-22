# logistics_prelim v1

Choose one hotel id from hotel_shortlist in DATA for the requested hotel tier.

Return JSON:
- hotel_id: one id from hotel_shortlist
- reason: one sentence. Mention metro_nearby only when the row has it. A null metro_nearby is still allowed when it is the hotel for that area and tier.

Do not use stars. Do not invent a nightly rate. Transport is already listed; do not add a bus fare.
