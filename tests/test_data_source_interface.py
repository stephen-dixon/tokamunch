import numpy as np

from tokamunch import TokamapInterface


class FakeMapper:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def map(self, device, ids_path, args):
        self.calls.append((device, ids_path, args))
        return self.values[ids_path]


def test_tokamap_interface_map_passes_args() -> None:
    mapper = FakeMapper({"a/b": np.array([1, 2, 3])})
    iface = TokamapInterface(mapper, "mastu", shot=47125)

    out = iface.map("a/b")

    assert out.tolist() == [1, 2, 3]
    assert mapper.calls == [("mastu", "a/b", {"shot": 47125})]


def test_tokamap_interface_get_array_length_records_scalar() -> None:
    mapper = FakeMapper({"a/b": np.array(5)})
    iface = TokamapInterface(mapper, "mastu", shot=47125)

    assert iface.get_array_length("a/b") == 5


def test_tokamap_interface_get_array_length_returns_zero_on_missing_mapping() -> None:
    from tokamunch.data_source_interface import _MISSING_MAPPING_PREFIX

    class MissingMappingMapper:
        def map(self, device, ids_path, args):
            raise RuntimeError(f"{_MISSING_MAPPING_PREFIX} {ids_path}")

    iface = TokamapInterface(MissingMappingMapper(), "mastu")

    assert iface.get_array_length("a/b") == 0


def test_tokamap_interface_get_array_length_raises_on_unexpected_error() -> None:
    import pytest

    class RaisingMapper:
        def map(self, device, ids_path, args):
            raise RuntimeError("connection refused")

    iface = TokamapInterface(RaisingMapper(), "mastu")

    with pytest.raises(RuntimeError, match="connection refused"):
        iface.get_array_length("a/b")
