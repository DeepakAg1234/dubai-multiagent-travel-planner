# budget_adjust v1

Choose one alternative from the list in DATA. The alternative already has a computed saving and a new total.

Return JSON:
- kind: the alternative kind
- with_id: the replacement id, or null
- replaces_id: the id being replaced, or null

Pick an alternative whose new_total_aed is within the budget when one exists. Do not invent an alternative.
