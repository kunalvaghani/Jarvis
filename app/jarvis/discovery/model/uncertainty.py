"""Explicit bounded ranges. A numeric interval is not a fabricated probability."""
from pydantic import Field, model_validator
from ..contracts import Finite, StrictModel


class Interval(StrictModel):
    lower: Finite
    upper: Finite
    unit: str = Field(min_length=1, max_length=80)
    source_ref: str = Field(min_length=1, max_length=500)
    interpretation: str = Field(default='bounded range; no probability distribution asserted', max_length=500)

    @model_validator(mode='after')
    def ordered(self):
        if self.lower > self.upper:
            raise ValueError('uncertainty interval bounds are reversed')
        return self
