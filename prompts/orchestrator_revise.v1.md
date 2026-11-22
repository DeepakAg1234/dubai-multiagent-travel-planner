# orchestrator_revise v1

Read the review report and the scheduled ids in DATA. Decide what to drop.

Return JSON:
- excluded_ids: catalog ids to remove. Only ids listed under scheduled_ids. Always include a scheduled place whose operational_status is closed or reopening.
- notes: what changed in the themes or pace
- pace: "relaxed", "balanced", "packed", or null to leave pace alone

Do not clear a rule blocker by claiming the plan is fine. Do not invent ids.
