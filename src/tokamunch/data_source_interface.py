from __future__ import annotations

from typing import Any

from .plugin_api import MapperProtocol

# Prefix of the "no mapping defined" exception that libtokamap raises.
# Shared with mapping.py for consistent error classification.
_MISSING_MAPPING_PREFIX = "Mapping error: failed to find mapping for"


def _decode_s1_bytes(value: Any) -> Any:
    """Decode a numpy S1 byte array to a Python str; pass all other values through."""
    if hasattr(value, "dtype") and value.dtype == "S1":
        return value.tobytes().decode()
    return value


class TokamapInterface:
    def __init__(
        self,
        mapper: MapperProtocol,
        device: str,
        *,
        shot: int | None = None,
        extra_args: dict[str, Any] | None = None,
    ):
        self.mapper = mapper
        self.device = device
        self._args: dict[str, Any] = dict(extra_args or {})
        if shot is not None:
            self._args["shot"] = shot

    def get_array_length(self, ids_path: str) -> int:
        try:
            res = self.map(ids_path)
            if res is None:
                return 0
            return int(_decode_s1_bytes(res))
        except Exception as exc:
            if str(exc).startswith(_MISSING_MAPPING_PREFIX):
                return 0
            raise

    def map(self, ids_path: str) -> Any:
        return self.mapper.map(self.device, ids_path, self._args)
