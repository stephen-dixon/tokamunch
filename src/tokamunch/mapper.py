"""Backward-compatibility shim. Canonical location: tokamunch.mapping.mapper_factory."""

from .mapping.mapper_factory import (  # noqa: F401
    _create_libtokamap_mapper,
    create_mapper_from_config,
)
