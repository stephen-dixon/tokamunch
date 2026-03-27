"""Tests for tokamunch.profiling — call-stats and report rendering."""

from __future__ import annotations

import threading

from tokamunch.profiling import (
    CallStats,
    ProfileData,
    render_profile_report,
)


class TestCallStats:
    def test_initial_state(self) -> None:
        s = CallStats()
        assert s.count == 0
        assert s.total_s == 0.0
        assert s.mean_s == 0.0

    def test_record_single(self) -> None:
        s = CallStats()
        s.record(0.1)
        assert s.count == 1
        assert s.total_s == 0.1
        assert s.min_s == 0.1
        assert s.max_s == 0.1
        assert abs(s.mean_s - 0.1) < 1e-9

    def test_record_multiple(self) -> None:
        s = CallStats()
        s.record(0.1)
        s.record(0.3)
        s.record(0.2)
        assert s.count == 3
        assert abs(s.total_s - 0.6) < 1e-9
        assert s.min_s == 0.1
        assert s.max_s == 0.3
        assert abs(s.mean_s - 0.2) < 1e-9

    def test_thread_safe(self) -> None:
        """Concurrent record() calls must not lose counts."""
        s = CallStats()
        n = 200

        def _record() -> None:
            for _ in range(n):
                s.record(0.001)

        threads = [threading.Thread(target=_record) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert s.count == n * 10


class TestRenderProfileReport:
    def _make_data(self) -> ProfileData:
        data = ProfileData()
        data.phases.expansion_s = 0.5
        data.phases.mapping_s = 2.0
        data.phases.output_s = 0.1
        data.mapper_map.record(0.05)
        data.mapper_map.record(0.20)
        data.array_length.record(0.01)
        return data

    def test_returns_string(self) -> None:
        report = render_profile_report(self._make_data(), total_elapsed_s=3.0)
        assert isinstance(report, str)

    def test_contains_phase_labels(self) -> None:
        report = render_profile_report(self._make_data(), total_elapsed_s=3.0)
        assert "expansion" in report
        assert "mapping" in report
        assert "output" in report

    def test_contains_call_counts(self) -> None:
        report = render_profile_report(self._make_data(), total_elapsed_s=3.0)
        assert "2" in report  # mapper_map.count
        assert "1" in report  # array_length.count

    def test_no_calls_path(self) -> None:
        data = ProfileData()
        report = render_profile_report(data, total_elapsed_s=1.0)
        assert "no calls" in report

    def test_high_latency_hint(self) -> None:
        data = ProfileData()
        # Simulate a slow remote call: mean > 200ms
        data.mapper_map.record(0.5)
        data.mapper_map.record(0.4)
        report = render_profile_report(data, total_elapsed_s=1.0)
        assert "latency" in report.lower()

    def test_fast_calls_hint(self) -> None:
        data = ProfileData()
        data.mapper_map.record(0.001)
        report = render_profile_report(data, total_elapsed_s=0.1)
        assert "cpu" in report.lower() or "fast" in report.lower()
