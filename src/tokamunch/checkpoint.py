"""Backward-compatibility shim. Canonical location: tokamunch.core.checkpoint."""

from .core.checkpoint import (  # noqa: F401
    CHECKPOINT_VERSION,
    Checkpoint,
    apply_checkpoint,
    load_checkpoint,
    save_checkpoint,
)
