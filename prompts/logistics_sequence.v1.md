# logistics_sequence v1

The day clusters in DATA are already ordered by the deterministic sequencer. You only break ties and name themes.

Return JSON:
- themes: one theme string per day, in day order
- place_order: place ids in the order to prefer when two stops are the same distance. Use only ids from the clusters.

Do not restate opening hours. Do not drop a satellite place off its day. Meals and the hotel stay in a planning area.
