"""Deterministic supervisory aggregation with an aggregate-only access boundary."""

from packages.suptech.aggregation import (
    build_adoption_view,
    build_gap_view,
    build_posture_view,
)

__all__ = ["build_adoption_view", "build_gap_view", "build_posture_view"]
