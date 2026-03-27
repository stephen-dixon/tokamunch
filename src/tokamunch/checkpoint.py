"""Checkpointing support for long-running munchi map operations.

Checkpoints allow interrupted mapping runs to be resumed from where they
left off, avoiding re-querying paths that have already been mapped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .mapping import MappingRecord

CHECKPOINT_VERSION = 1


@dataclass
class Checkpoint:
    """Persistent state for a partially-completed mapping run."""

    output_path: str
    """The target output file this checkpoint corresponds to."""

    completed_paths: list[str] = field(default_factory=list)
    """Concrete paths whose mapping has already been stored."""

    results: dict[str, Any] = field(default_factory=dict)
    """path → JSON-safe value for each completed path."""


def load_checkpoint(path: Path) -> Checkpoint | None:
    """Load a checkpoint from *path*.

    Returns ``None`` if the file does not exist.  Raises ``ValueError`` if
    the file exists but cannot be parsed as a valid checkpoint.
    """
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Checkpoint file {path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Checkpoint file {path} must contain a JSON object")

    version = raw.get("version", 1)
    if version != CHECKPOINT_VERSION:
        raise ValueError(
            f"Unsupported checkpoint version {version!r} in {path}. "
            f"Expected version {CHECKPOINT_VERSION}."
        )

    return Checkpoint(
        output_path=raw.get("output_path", ""),
        completed_paths=raw.get("completed_paths", []),
        results=raw.get("results", {}),
    )


def save_checkpoint(path: Path, cp: Checkpoint) -> None:
    """Write *cp* to *path* atomically (write to a .tmp file then rename).

    The parent directory is created if it does not already exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    data = {
        "version": CHECKPOINT_VERSION,
        "output_path": cp.output_path,
        "completed_paths": cp.completed_paths,
        "results": cp.results,
    }
    tmp_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    tmp_path.replace(path)


def apply_checkpoint(
    paths: list[str],
    cp: Checkpoint,
) -> tuple[list[str], list[MappingRecord]]:
    """Split *paths* into remaining work and already-completed records.

    Parameters
    ----------
    paths:
        Full list of concrete paths to be mapped.
    cp:
        Previously saved checkpoint.

    Returns
    -------
    remaining_paths:
        Paths NOT already in ``cp.completed_paths``.
    already_done_records:
        ``MappingRecord`` instances for every path that was already completed,
        with values restored from ``cp.results``.
    """
    completed_set = set(cp.completed_paths)
    remaining: list[str] = []
    done_records: list[MappingRecord] = []

    for path in paths:
        if path in completed_set:
            value = cp.results.get(path)
            done_records.append(MappingRecord(ids_path=path, value=value))
        else:
            remaining.append(path)

    return remaining, done_records
