from __future__ import annotations

from typing import Any

# The prefix of the "no mapping defined" exception that libtokamap raises.
# Shared with mapping.py for consistent error classification.
_MISSING_MAPPING_PREFIX = "Mapping error: failed to find mapping for"


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
        except Exception as exc:
            if str(exc).startswith(_MISSING_MAPPING_PREFIX):
                # No mapping defined for this array — treat as length 0.
                return 0
            # Any other exception (connection failure, auth error, etc.) is
            # unexpected: re-raise so the caller can handle it explicitly
            # rather than silently producing an empty expansion.
            raise

    def map(self, ids_path: str) -> Any:
        return self.mapper.map(self.device, ids_path, self.args)
