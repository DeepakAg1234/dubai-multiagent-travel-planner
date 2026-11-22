# destination_research v1

Pick places and restaurants from the shortlist in DATA. The shortlist is already scored. Explain the pick. Do not add ids that are absent from the shortlist.

Return JSON:
- place_ids: ids from place_shortlist, open places only
- restaurant_ids: ids from restaurant_shortlist
- reasons: one short sentence per chosen place, mentioning estimated when the row is estimated

A family interest may keep a Dubailand or Al Barsha place. Restaurants still have to be in a planning area. A food interest is satisfied by restaurants, not by a place tag. Ignore cuisine.
