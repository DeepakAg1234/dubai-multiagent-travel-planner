"""Small JSON schemas the LLM nodes fill. Python applies catalog rules after."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParseDraft(BaseModel):
    days: int | None = None
    budget_aed: float | None = None
    travelers: int | None = None
    interests: list[str] = Field(default_factory=list)
    hotel_tier: str | None = None
    avoid_crowds: bool = False
    pace: str | None = None
    start_date: str | None = None
    assumptions: list[str] = Field(default_factory=list)


class ResearchPick(BaseModel):
    place_ids: list[str] = Field(default_factory=list)
    restaurant_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class StayPick(BaseModel):
    hotel_id: str = ""
    reason: str = ""


class SequenceDraft(BaseModel):
    themes: list[str] = Field(default_factory=list)
    place_order: list[str] = Field(default_factory=list)


class BudgetNarration(BaseModel):
    summary: str = ""
    uncertainty: list[str] = Field(default_factory=list)


class AdjustChoice(BaseModel):
    kind: str = ""
    with_id: str | None = None
    replaces_id: str | None = None


class Qualitative(BaseModel):
    warnings: list[str] = Field(default_factory=list)
    request_revision: bool = False
    note: str = ""


class FinalNarrative(BaseModel):
    narrative: str = ""
    provenance_notes: list[str] = Field(default_factory=list)


class ReviseDraft(BaseModel):
    excluded_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    pace: str | None = None
