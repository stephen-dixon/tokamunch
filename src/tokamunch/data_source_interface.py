from __future__ import annotations

from typing import Any


class TokamapInterface:
    def __init__(self, mapper: Any, device: str, args: dict[str, Any] | None = None):
        self.mapper = mapper
        self.device = device
        self.args = args or {}

    def get_array_length(self, ids_path: str) -> int:
        try:
            res = self.map(ids_path)
            if res is None:
                return 0

            if hasattr(res, "dtype") and res.dtype == "S1":
                res = res.tobytes().decode()

            return int(res)
        except Exception:
            return 0

    def map(self, ids_path: str) -> Any:
        return self.mapper.map(self.device, ids_path, self.args)
