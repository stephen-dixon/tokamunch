from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from .plugin_api import MapperProtocol

if TYPE_CHECKING:
    from .profiling import ProfileData

logger = logging.getLogger(__name__)

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
        # Set externally to enable per-call timing (see profiling.py).
        self.profile: ProfileData | None = None

    def get_array_length(self, ids_path: str) -> int:
        t0 = time.perf_counter() if self.profile is not None else 0.0
        try:
            res = self.map(ids_path)
            if res is None:
                return 0
            scalar = _decode_s1_bytes(res)
            try:
                if hasattr(scalar, "item"):
                    scalar = scalar.item()
                return int(scalar)
            except (ValueError, TypeError) as cast_exc:
                dtype = getattr(scalar, "dtype", type(scalar).__name__)
                shape = getattr(scalar, "shape", None)
                logger.debug(
                    "Array-length cast failed for %r: %s. "
                    "type=%s dtype=%s shape=%s value=%r",
                    ids_path,
                    cast_exc,
                    type(scalar).__name__,
                    dtype,
                    shape,
                    scalar,
                )
                raise
        except Exception as exc:
            if str(exc).startswith(_MISSING_MAPPING_PREFIX):
                return 0
            if isinstance(exc, SystemError):
                # libtokamap's C-level map() sometimes returns a value while also
                # having an exception set — CPython converts that to a SystemError.
                # Treat it as "unknown length" so expansion continues rather than
                # crashing the whole run.
                logger.warning(
                    "C-level error from mapper during array-length query for %r: %s — "
                    "treating as length 0 (paths under this array will not be expanded)",
                    ids_path,
                    exc,
                )
                return 0
            raise
        finally:
            if self.profile is not None:
                self.profile.array_length.record(time.perf_counter() - t0)

    def map(self, ids_path: str) -> Any:
        if self.profile is not None:
            t0 = time.perf_counter()
            result = self.mapper.map(self.device, ids_path, self._args)
            self.profile.mapper_map.record(time.perf_counter() - t0)
            return result
        return self.mapper.map(self.device, ids_path, self._args)
