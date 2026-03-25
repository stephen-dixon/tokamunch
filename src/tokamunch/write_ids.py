from __future__ import annotations

from pathlib import Path
from typing import Any


def write_h5_output(path: Path, *, records: list[Any], force: bool) -> None:
    raise NotImplementedError(
        f"Writing mapped IDS data to {path} is not implemented yet."
    )
