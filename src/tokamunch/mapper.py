from __future__ import annotations

from typing import Any

import libtokamap

from .config import CLIConfig
from .plugins import load_data_source_factory


def create_mapper_from_config(config: CLIConfig) -> libtokamap.Mapper:
    mapper = libtokamap.Mapper(config.mapper.config)

    for ds in config.data_sources:
        if not ds.enabled:
            continue

        factory = load_data_source_factory(ds.plugin)
        data_source = factory(ds.args)

        mapper.register_python_data_source(ds.mapper_name, data_source)

    return mapper
