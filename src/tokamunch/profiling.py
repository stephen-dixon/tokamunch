"""Profiling data structures and report rendering for tokamunch runs."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class CallStats:
    """Thread-safe accumulator for per-call timing statistics."""

    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False, compare=False
    )
    count: int = 0
    total_s: float = 0.0
    min_s: float = float("inf")
    max_s: float = 0.0

    def record(self, elapsed_s: float) -> None:
        with self._lock:
            self.count += 1
            self.total_s += elapsed_s
            if elapsed_s < self.min_s:
                self.min_s = elapsed_s
            if elapsed_s > self.max_s:
                self.max_s = elapsed_s

    @property
    def mean_s(self) -> float:
        return self.total_s / self.count if self.count else 0.0


@dataclass
class PhaseTimings:
    expansion_s: float = 0.0
    mapping_s: float = 0.0
    output_s: float = 0.0


@dataclass
class ProfileData:
    phases: PhaseTimings = field(default_factory=PhaseTimings)
    mapper_map: CallStats = field(default_factory=CallStats)
    array_length: CallStats = field(default_factory=CallStats)


def _ascii_bar(frac: float, width: int = 20) -> str:
    filled = int(min(frac, 1.0) * width)
    return f"[{'#' * filled}{'.' * (width - filled)}]"


def render_profile_report(data: ProfileData, total_elapsed_s: float) -> str:
    lines: list[str] = []
    lines.append("── Profiling report ──────────────────────────────────────────")

    # Phase breakdown
    p = data.phases
    phase_accounted = p.expansion_s + p.mapping_s + p.output_s
    overhead_s = max(0.0, total_elapsed_s - phase_accounted)

    lines.append("")
    lines.append("Phase breakdown:")
    for label, t in [
        ("path expansion (incl. array-length queries)", p.expansion_s),
        ("mapping (mapper.map calls)                 ", p.mapping_s),
        ("output / file write                        ", p.output_s),
        ("overhead / other                           ", overhead_s),
    ]:
        frac = t / total_elapsed_s if total_elapsed_s > 0 else 0.0
        bar = _ascii_bar(frac)
        lines.append(f"  {bar} {frac:5.1%}  {t:.3f}s  {label}")

    lines.append(f"  total: {total_elapsed_s:.3f}s")

    # mapper.map() call statistics
    mm = data.mapper_map
    al = data.array_length
    lines.append("")
    lines.append("Call statistics:")
    if mm.count == 0:
        lines.append("  mapper.map()       (no calls)")
    else:
        lines.append(
            f"  mapper.map()       calls={mm.count:>7}  total={mm.total_s:.3f}s"
            f"  mean={mm.mean_s * 1000:.1f}ms"
            f"  min={mm.min_s * 1000:.1f}ms"
            f"  max={mm.max_s * 1000:.1f}ms"
        )
    if al.count == 0:
        lines.append("  get_array_length() (no calls)")
    else:
        lines.append(
            f"  get_array_length() calls={al.count:>7}  total={al.total_s:.3f}s"
            f"  mean={al.mean_s * 1000:.1f}ms"
            f"  min={al.min_s * 1000:.1f}ms"
            f"  max={al.max_s * 1000:.1f}ms"
        )

    # Bottleneck hints
    lines.append("")
    lines.append("Bottleneck hints:")
    hints: list[str] = []

    if mm.count > 0:
        mean_ms = mm.mean_s * 1000
        if mean_ms > 200:
            hints.append(
                f"  mapper.map() mean={mean_ms:.0f}ms — strongly latency-bound "
                "(network or remote file I/O in the data source plugin). "
                "Use --concurrency-mode thread or process to parallelise."
            )
        elif mean_ms > 20:
            hints.append(
                f"  mapper.map() mean={mean_ms:.0f}ms — moderate latency. "
                "Consider --concurrency-mode thread or process."
            )
        else:
            hints.append(
                f"  mapper.map() mean={mean_ms:.1f}ms — fast; "
                "likely CPU-bound or local. Threading may not help much."
            )

    if al.count > 0 and p.expansion_s > 0.5:
        pct = p.expansion_s / total_elapsed_s * 100 if total_elapsed_s > 0 else 0.0
        hints.append(
            f"  {al.count} array-length queries dominate expansion "
            f"({p.expansion_s:.2f}s, {pct:.0f}% of total). "
            "Consider --leaves-only or --mapping to reduce path count, "
            "or add caching to the data source plugin."
        )

    if mm.count > 0 and al.count > 0:
        map_fraction = (mm.count - al.count) / mm.count
        if map_fraction < 0.3:
            hints.append(
                f"  Most mapper.map() calls ({al.count}/{mm.count}) are array-length "
                "queries, not data reads. Reducing IDS depth with --leaves-only "
                "may speed up expansion significantly."
            )

    if not hints:
        hints.append("  No obvious bottlenecks detected.")
    lines.extend(hints)

    lines.append("──────────────────────────────────────────────────────────────")
    return "\n".join(lines)
