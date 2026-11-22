"""Shared value types."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Provenance = Literal["verified", "api", "estimated"]


class Sourced(BaseModel):
    """A fact that records where it came from and how much to trust it."""

    provenance: Provenance
    source: str = Field(min_length=1)
    as_of: date | None = None


class PriceRange(BaseModel):
    """An inclusive AED range. A single known price uses equal ends."""

    min_aed: float = Field(ge=0)
    max_aed: float = Field(ge=0)

    @model_validator(mode="after")
    def max_covers_min(self) -> "PriceRange":
        if self.max_aed < self.min_aed:
            raise ValueError("max_aed is below min_aed")
        return self


class ToolResult[T](BaseModel):
    """Result contract for every agent-facing tool."""

    data: T
    provenance: Provenance
    source: str = Field(min_length=1)
    degraded: bool = False
    error: str | None = None
