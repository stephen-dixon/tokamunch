import pytest

from tokamunch.mapping import (
    MappingRecord,
    MappingSummary,
    _build_records,
    normalise_map_result,
    should_suppress_mapping_error,
)
from tokamunch.data_source_interface import _MISSING_MAPPING_PREFIX


class TestNormaliseMapResult:
    def test_none_passthrough(self) -> None:
        assert normalise_map_result(None) is None

    def test_scalar_passthrough(self) -> None:
        assert normalise_map_result(42) == 42
        assert normalise_map_result(3.14) == 3.14
        assert normalise_map_result("hello") == "hello"

    def test_decodes_s1_numpy_array(self) -> None:
        import numpy as np
        arr = np.frombuffer(b"hello", dtype="S1")
        assert normalise_map_result(arr) == "hello"

    def test_non_s1_numpy_array_passthrough(self) -> None:
        import numpy as np
        arr = np.array([1, 2, 3])
        result = normalise_map_result(arr)
        assert (result == arr).all()


class TestShouldSuppressMappingError:
    def test_suppresses_missing_mapping_error(self) -> None:
        exc = RuntimeError(f"{_MISSING_MAPPING_PREFIX} some/ids/path")
        assert should_suppress_mapping_error(exc) is True

    def test_does_not_suppress_other_errors(self) -> None:
        assert should_suppress_mapping_error(RuntimeError("connection refused")) is False
        assert should_suppress_mapping_error(ValueError("bad value")) is False

    def test_prefix_must_match_exactly(self) -> None:
        # A message containing the prefix but not starting with it must not be suppressed.
        exc = RuntimeError(f"wrapped: {_MISSING_MAPPING_PREFIX} path")
        assert should_suppress_mapping_error(exc) is False


class TestBuildRecords:
    def test_successful_mapping(self) -> None:
        raw = [("a/b", 42, None)]
        records, summary = _build_records(raw, verbose_errors=False)

        assert len(records) == 1
        assert records[0].ids_path == "a/b"
        assert records[0].value == 42
        assert records[0].ok is True
        assert summary.mapped == 1
        assert summary.total_paths == 1

    def test_none_value(self) -> None:
        raw = [("a/b", None, None)]
        records, summary = _build_records(raw, verbose_errors=False)

        assert records[0].value is None
        assert records[0].ok is True
        assert summary.returned_none == 1
        assert summary.mapped == 0

    def test_suppressed_error(self) -> None:
        exc = RuntimeError(f"{_MISSING_MAPPING_PREFIX} a/b")
        raw = [("a/b", None, exc)]
        records, summary = _build_records(raw, verbose_errors=False)

        assert records[0].suppressed is True
        assert summary.suppressed_errors == 1
        assert summary.unexpected_errors == 0

    def test_suppressed_error_shown_when_verbose(self) -> None:
        exc = RuntimeError(f"{_MISSING_MAPPING_PREFIX} a/b")
        raw = [("a/b", None, exc)]
        records, summary = _build_records(raw, verbose_errors=True)

        assert records[0].suppressed is False
        assert summary.suppressed_errors == 0
        assert summary.unexpected_errors == 1

    def test_unexpected_error(self) -> None:
        exc = RuntimeError("network timeout")
        raw = [("a/b", None, exc)]
        records, summary = _build_records(raw, verbose_errors=False)

        assert records[0].suppressed is False
        assert records[0].error is exc
        assert summary.unexpected_errors == 1

    def test_mixed_results(self) -> None:
        suppressed_exc = RuntimeError(f"{_MISSING_MAPPING_PREFIX} c/d")
        raw = [
            ("a/b", 1, None),
            ("b/c", None, None),
            ("c/d", None, suppressed_exc),
            ("d/e", None, RuntimeError("boom")),
        ]
        records, summary = _build_records(raw, verbose_errors=False)

        assert summary.total_paths == 4
        assert summary.mapped == 1
        assert summary.returned_none == 1
        assert summary.suppressed_errors == 1
        assert summary.unexpected_errors == 1
        assert summary.has_unexpected_errors is True
