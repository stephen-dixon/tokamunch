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
    iface = TokamapInterface(mapper, "mastu", {"shot": 47125})

    out = iface.map("a/b")

    assert out.tolist() == [1, 2, 3]
    assert mapper.calls == [("mastu", "a/b", {"shot": 47125})]


def test_tokamap_interface_get_array_length_records_scalar() -> None:
    mapper = FakeMapper({"a/b": np.array(5)})
    iface = TokamapInterface(mapper, "mastu", {"shot": 47125})

    n = iface.get_array_length("a/b")

    assert n == 5


def test_tokamap_interface_get_array_length_returns_zero_on_error() -> None:
    class RaisingMapper:
        def map(self, device, ids_path, args):
            raise RuntimeError("boom")

    iface = TokamapInterface(RaisingMapper(), "mastu", {})

    assert iface.get_array_length("a/b") == 0
