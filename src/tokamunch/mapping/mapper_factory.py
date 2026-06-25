"""Create libtokamap Mapper instances from CLIConfig."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from typing import Any

import libtokamap

from ..core.config import CLIConfig, ConcurrencyMode
from ..plugins.registry import load_plugin

logger = logging.getLogger(__name__)


def _create_libtokamap_mapper(
    config: str | None, config_params: dict[str, Any] | None
) -> libtokamap.Mapper:
    """Create a libtokamap Mapper from either a config file path or an in-memory dict.

    When ``config_params`` is provided, the dict is written to a temporary JSON
    file which is deleted immediately after the Mapper is initialised.  Once
    libtokamap gains native in-memory initialisation this shim can be replaced
    with a direct call.
    """
    if config is not None:
        return libtokamap.Mapper(config)

    # In-memory path: serialise to a temp file, init, then clean up.
    assert config_params is not None
    fd, tmp_path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(config_params, f)
        return libtokamap.Mapper(tmp_path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)


def create_mapper_from_config(config: CLIConfig) -> libtokamap.Mapper:
    mapper = _create_libtokamap_mapper(
        config.mapper.config, config.mapper.config_params
    )

    concurrency_mode = config.run.concurrency.mode

    for ds in config.data_sources:
        if not ds.enabled:
            continue

        plugin = load_plugin(ds.plugin)

        if (
            concurrency_mode == ConcurrencyMode.THREAD
            and not plugin.metadata.thread_safe
        ):
            logger.warning(
                "Plugin %r is not thread-safe but thread concurrency is enabled. "
                "Consider switching to 'process' concurrency mode or verify that "
                "the plugin is safe to use across threads.",
                ds.plugin,
            )

        data_source = plugin.factory(ds.args)
        mapper.register_python_data_source(ds.mapper_name, data_source)

    return mapper
