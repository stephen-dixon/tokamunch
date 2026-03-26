from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


class ConcurrencyMode(str, Enum):
    SERIAL = "serial"
    THREAD = "thread"
    PROCESS = "process"


@dataclass(slots=True)
class ConcurrencyConfig:
    mode: ConcurrencyMode = ConcurrencyMode.SERIAL
    workers: int = 1


@dataclass(slots=True)
class DataSourceConfig:
    mapper_name: str
    plugin: str
    enabled: bool = True
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MapperConfig:
    config: str
    device: str


@dataclass(slots=True)
class RunConfig:
    default_shot: int | None = None
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)


@dataclass(slots=True)
class CLIConfig:
    mapper: MapperConfig
    run: RunConfig
    data_sources: list[DataSourceConfig]


def load_cli_config(path: str | Path) -> CLIConfig:
    config_path = Path(path)
    with config_path.open("rb") as f:
        raw = tomllib.load(f)

    mapper_raw = raw.get("mapper", {})
    run_raw = raw.get("run", {})
    data_sources_raw = raw.get("data_sources", {})

    mapper_config_file: str = mapper_raw["config"]
    mapper_config_path = Path(mapper_config_file)
    if not mapper_config_path.exists():
        raise FileNotFoundError(
            f"Mapper config file not found: {mapper_config_path!r} "
            f"(from 'mapper.config' in {config_path})"
        )

    mapper = MapperConfig(
        config=mapper_config_file,
        device=mapper_raw["device"],
    )

    concurrency_raw = run_raw.get("concurrency", {})
    concurrency = ConcurrencyConfig(
        mode=ConcurrencyMode(concurrency_raw.get("mode", ConcurrencyMode.SERIAL)),
        workers=int(concurrency_raw.get("workers", 1)),
    )

    run = RunConfig(
        default_shot=run_raw.get("default_shot"),
        concurrency=concurrency,
    )

    data_sources: list[DataSourceConfig] = []

    for mapper_name, ds_raw in data_sources_raw.items():
        ds_raw = dict(ds_raw)

        plugin = ds_raw.pop("plugin")
        enabled = ds_raw.pop("enabled", True)
        args = ds_raw.pop("args", {})

        if ds_raw:
            raise ValueError(
                f"Unexpected keys in data_sources.{mapper_name}: {list(ds_raw.keys())}"
            )

        data_sources.append(
            DataSourceConfig(
                mapper_name=mapper_name,
                plugin=plugin,
                enabled=enabled,
                args=args,
            )
        )

    return CLIConfig(
        mapper=mapper,
        run=run,
        data_sources=data_sources,
    )


def render_cli_config_template() -> str:
    return """# Skeleton munchi configuration file
# Fill in the values for your local setup.

[mapper]
config = "mapping.json"
device = "mast"

[run]
default_shot = 0

# Concurrency settings (optional).
# mode:    "serial"  — sequential, always safe (default)
#          "thread"  — shared mapper across threads; only use if all plugins are thread-safe
#          "process" — each worker spawns its own mapper; safe for all plugins
# workers: number of parallel workers (ignored when mode = "serial")
#
# [run.concurrency]
# mode = "process"
# workers = 8

# Each data source entry is keyed by the mapper data-source name.
# Add, remove, or duplicate sections as required.
#
# [data_sources.pyuda]
# plugin = "pyuda"
# enabled = true
# args = { host = "localhost", port = 56565, plugin_name = "uda" }
"""
