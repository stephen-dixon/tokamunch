"""Backward-compatibility shim. Canonical location: tokamunch.core.profiling."""

from .core.profiling import (  # noqa: F401
    CallStats,
    PhaseTimings,
    ProfileData,
    render_profile_report,
)
