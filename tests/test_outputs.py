import base64

import numpy as np

from tokamunch.mapping import MappingRecord
from tokamunch.outputs import (
    build_json_results,
    make_json_safe,
    render_text_records,
)


class TestMakeJsonSafe:
    def test_primitives_passthrough(self) -> None:
        assert make_json_safe(None) is None
        assert make_json_safe(42) == 42
        assert make_json_safe(3.14) == 3.14
        assert make_json_safe("hello") == "hello"
        assert make_json_safe(True) is True

    def test_list_recursed(self) -> None:
        assert make_json_safe([1, "a", None]) == [1, "a", None]

    def test_tuple_becomes_list(self) -> None:
        assert make_json_safe((1, 2)) == [1, 2]

    def test_dict_with_non_string_keys(self) -> None:
        result = make_json_safe({1: "a", 2: "b"})
        assert result == {"1": "a", "2": "b"}

    def test_numpy_1d_array(self) -> None:
        import numpy as np

        arr = np.array([1.0, 2.0, 3.0])
        result = make_json_safe(arr)
        assert result == [1.0, 2.0, 3.0]

    def test_numpy_2d_array(self) -> None:
        import numpy as np

        arr = np.array([[1, 2], [3, 4]])
        result = make_json_safe(arr)
        assert result == [[1, 2], [3, 4]]

    def test_numpy_scalar(self) -> None:
        import numpy as np

        val = np.float64(3.14)
        result = make_json_safe(val)
        assert isinstance(result, float)
        assert abs(result - 3.14) < 1e-6

    def test_unknown_type_falls_back_to_str(self) -> None:
        class Opaque:
            def __str__(self):
                return "opaque"

        assert make_json_safe(Opaque()) == "opaque"


class TestMakeJsonSafeBinaryArrays:
    def test_1d_array_encoded_as_dict(self) -> None:
        arr = np.array([1.0, 2.0, 3.0])
        result = make_json_safe(arr, binary_arrays=True)
        assert isinstance(result, dict)
        assert "__ndarray__" in result
        assert "dtype" in result
        assert "shape" in result

    def test_shape_preserved(self) -> None:
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = make_json_safe(arr, binary_arrays=True)
        assert result["shape"] == [2, 2]

    def test_dtype_preserved(self) -> None:
        arr = np.array([1, 2, 3], dtype=np.int32)
        result = make_json_safe(arr, binary_arrays=True)
        assert result["dtype"] == "int32"

    def test_binary_roundtrip(self) -> None:
        arr = np.array([1.5, 2.5, 3.5], dtype=np.float64)
        encoded = make_json_safe(arr, binary_arrays=True)
        raw = base64.b64decode(encoded["__ndarray__"])
        decoded = np.frombuffer(raw, dtype=encoded["dtype"]).reshape(encoded["shape"])
        np.testing.assert_array_equal(decoded, arr)

    def test_primitives_unaffected_by_binary_flag(self) -> None:
        assert make_json_safe(42, binary_arrays=True) == 42
        assert make_json_safe("hello", binary_arrays=True) == "hello"
        assert make_json_safe(None, binary_arrays=True) is None

    def test_list_of_arrays_encoded_when_binary(self) -> None:
        arr = np.array([1.0])
        result = make_json_safe([arr], binary_arrays=True)
        assert isinstance(result[0], dict)
        assert "__ndarray__" in result[0]

    def test_default_flag_false_gives_list(self) -> None:
        arr = np.array([1.0, 2.0])
        result = make_json_safe(arr)
        assert result == [1.0, 2.0]


class TestBuildJsonResultsBinaryArrays:
    def test_binary_flag_propagates(self) -> None:
        arr = np.array([1.0, 2.0])
        records = [MappingRecord(ids_path="magnetics/time", value=arr)]
        result = build_json_results(records, binary_arrays=True)
        assert isinstance(result["magnetics/time"], dict)
        assert "__ndarray__" in result["magnetics/time"]

    def test_default_binary_false_gives_list(self) -> None:
        arr = np.array([1.0, 2.0])
        records = [MappingRecord(ids_path="magnetics/time", value=arr)]
        result = build_json_results(records)
        assert result["magnetics/time"] == [1.0, 2.0]


class TestBuildJsonResults:
    def test_includes_successful_mappings(self) -> None:
        records = [
            MappingRecord(ids_path="a/b", value=1),
            MappingRecord(ids_path="c/d", value="x"),
        ]
        result = build_json_results(records)
        assert result == {"a/b": 1, "c/d": "x"}

    def test_excludes_none_values(self) -> None:
        records = [MappingRecord(ids_path="a/b", value=None)]
        assert build_json_results(records) == {}

    def test_excludes_error_records(self) -> None:
        records = [MappingRecord(ids_path="a/b", error=RuntimeError("boom"))]
        assert build_json_results(records) == {}


class TestRenderTextRecords:
    def test_successful_records_shown(self) -> None:
        records = [MappingRecord(ids_path="a/b", value=42)]
        assert render_text_records(records, verbose_errors=False) == "a/b: 42"

    def test_none_values_omitted(self) -> None:
        records = [MappingRecord(ids_path="a/b", value=None)]
        assert render_text_records(records, verbose_errors=False) == ""

    def test_suppressed_errors_hidden_by_default(self) -> None:
        exc = RuntimeError("suppressed")
        records = [MappingRecord(ids_path="a/b", error=exc, suppressed=True)]
        assert render_text_records(records, verbose_errors=False) == ""

    def test_suppressed_errors_shown_when_verbose(self) -> None:
        exc = RuntimeError("suppressed")
        records = [MappingRecord(ids_path="a/b", error=exc, suppressed=True)]
        output = render_text_records(records, verbose_errors=True)
        assert "a/b" in output

    def test_unsuppressed_errors_always_shown(self) -> None:
        exc = RuntimeError("connection refused")
        records = [MappingRecord(ids_path="a/b", error=exc, suppressed=False)]
        output = render_text_records(records, verbose_errors=False)
        assert "a/b" in output
