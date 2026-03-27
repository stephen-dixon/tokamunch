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
    device: str
    # Exactly one of these must be set.
    # config:        path to a libtokamap config file (JSON or TOML).
    # config_params: inline libtokamap config as a dict (passed in-memory).
    config: str | None = None
    config_params: dict[str, Any] | None = None


@dataclass(slots=True)
class RunConfig:
    default_shot: int | None = None
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    log_level: str = "WARNING"
    binary_arrays: bool = False
    on_imas_error: str = "fallback-json"  # "fallback-json" | "raise"


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

    mapper_config_file: str | None = mapper_raw.get("config")
    mapper_config_params: dict[str, Any] | None = mapper_raw.get("config_params")

    if mapper_config_file is not None and mapper_config_params is not None:
        raise ValueError(
            f"'mapper.config' and 'mapper.config_params' are mutually exclusive in {config_path}. "
            "Use one or the other."
        )
    if mapper_config_file is None and mapper_config_params is None:
        raise ValueError(
            f"One of 'mapper.config' (file path) or 'mapper.config_params' (inline table) "
            f"must be set in {config_path}."
        )

    if mapper_config_file is not None:
        mapper_config_path = Path(mapper_config_file)
        if not mapper_config_path.exists():
            raise FileNotFoundError(
                f"Mapper config file not found: {mapper_config_path!r} "
                f"(from 'mapper.config' in {config_path})"
            )

    mapper = MapperConfig(
        device=mapper_raw["device"],
        config=mapper_config_file,
        config_params=mapper_config_params,
    )

    concurrency_raw = run_raw.get("concurrency", {})
    concurrency = ConcurrencyConfig(
        mode=ConcurrencyMode(concurrency_raw.get("mode", "serial")),
        workers=int(concurrency_raw.get("workers", 1)),
    )

    log_level_raw = str(run_raw.get("log_level", "WARNING")).upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level_raw not in valid_levels:
        raise ValueError(
            f"Invalid 'run.log_level' value {log_level_raw!r} in {config_path}. "
            f"Must be one of: {', '.join(sorted(valid_levels))}"
        )

    binary_arrays = bool(run_raw.get("binary_arrays", False))

    on_imas_error_raw = str(run_raw.get("on_imas_error", "fallback-json")).lower()
    valid_on_imas_error = {"fallback-json", "raise"}
    if on_imas_error_raw not in valid_on_imas_error:
        raise ValueError(
            f"Invalid 'run.on_imas_error' value {on_imas_error_raw!r} in {config_path}. "
            f"Must be one of: {', '.join(sorted(valid_on_imas_error))}"
        )

    run = RunConfig(
        default_shot=run_raw.get("default_shot"),
        concurrency=concurrency,
        log_level=log_level_raw,
        binary_arrays=binary_arrays,
        on_imas_error=on_imas_error_raw,
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


def apply_config_overrides(cfg: CLIConfig, overrides: list[str]) -> CLIConfig:
    """Apply ``dotted.key=value`` overrides to a CLIConfig, returning a new instance.

    Supported keys:
        run.concurrency.mode       → ConcurrencyMode
        run.concurrency.workers    → int
        run.log_level              → str (must be a valid log level)
        run.binary_arrays          → bool ("true"/"false"/"1"/"0")
        run.on_imas_error          → str ("fallback-json" or "raise")
        run.default_shot           → int
        mapper.device              → str

    Since all dataclasses use ``slots=True``, new instances are constructed
    rather than mutating the originals.

    Raises
    ------
    ValueError
        For unknown keys or invalid values.
    """

    if not overrides:
        return cfg

    # Unpack current state so we can build new instances.
    mapper_device = cfg.mapper.device
    mapper_config = cfg.mapper.config
    mapper_config_params = cfg.mapper.config_params

    run_default_shot = cfg.run.default_shot
    run_log_level = cfg.run.log_level
    run_binary_arrays = cfg.run.binary_arrays
    run_on_imas_error = cfg.run.on_imas_error
    conc_mode = cfg.run.concurrency.mode
    conc_workers = cfg.run.concurrency.workers

    valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    valid_on_imas_error = {"fallback-json", "raise"}

    def _parse_bool(raw: str) -> bool:
        if raw.lower() in ("true", "1"):
            return True
        if raw.lower() in ("false", "0"):
            return False
        raise ValueError(f"Expected true/false/1/0, got {raw!r}")

    for override in overrides:
        if "=" not in override:
            raise ValueError(
                f"Invalid override {override!r}: expected KEY=VALUE format"
            )
        key, _, raw_value = override.partition("=")
        key = key.strip()

        if key == "run.concurrency.mode":
            try:
                conc_mode = ConcurrencyMode(raw_value)
            except ValueError as err:
                valid = [m.value for m in ConcurrencyMode]
                raise ValueError(
                    f"Invalid run.concurrency.mode {raw_value!r}. "
                    f"Must be one of: {', '.join(valid)}"
                ) from err
        elif key == "run.concurrency.workers":
            try:
                conc_workers = int(raw_value)
            except ValueError as err:
                raise ValueError(
                    f"Invalid run.concurrency.workers {raw_value!r}: expected an integer"
                ) from err
        elif key == "run.log_level":
            run_log_level = raw_value.upper()
            if run_log_level not in valid_log_levels:
                raise ValueError(
                    f"Invalid run.log_level {raw_value!r}. "
                    f"Must be one of: {', '.join(sorted(valid_log_levels))}"
                )
        elif key == "run.binary_arrays":
            run_binary_arrays = _parse_bool(raw_value)
        elif key == "run.on_imas_error":
            if raw_value not in valid_on_imas_error:
                raise ValueError(
                    f"Invalid run.on_imas_error {raw_value!r}. "
                    f"Must be one of: {', '.join(sorted(valid_on_imas_error))}"
                )
            run_on_imas_error = raw_value
        elif key == "run.default_shot":
            try:
                run_default_shot = int(raw_value)
            except ValueError as err:
                raise ValueError(
                    f"Invalid run.default_shot {raw_value!r}: expected an integer"
                ) from err
        elif key == "mapper.device":
            mapper_device = raw_value
        else:
            raise ValueError(
                f"Unknown config override key {key!r}. "
                "Supported keys: run.concurrency.mode, run.concurrency.workers, "
                "run.log_level, run.binary_arrays, run.on_imas_error, "
                "run.default_shot, mapper.device"
            )

    new_concurrency = ConcurrencyConfig(mode=conc_mode, workers=conc_workers)
    new_run = RunConfig(
        default_shot=run_default_shot,
        concurrency=new_concurrency,
        log_level=run_log_level,
        binary_arrays=run_binary_arrays,
        on_imas_error=run_on_imas_error,
    )
    new_mapper = MapperConfig(
        device=mapper_device,
        config=mapper_config,
        config_params=mapper_config_params,
    )
    return CLIConfig(
        mapper=new_mapper,
        run=new_run,
        data_sources=cfg.data_sources,
    )


def render_cli_config_template() -> str:
    return """# Skeleton munchi configuration file
# Fill in the values for your local setup.

[mapper]
device = "mast"

# Option A: point to a libtokamap config file (JSON or TOML).
config = "config.toml"

# Option B: supply libtokamap config inline (mutually exclusive with 'config').
# [mapper.config_params]
# mapping_directory = "/path/to/mappings"
# schemas_directory = "/path/to/schemas"
# trace = false
# cache = true

[run]
default_shot = 0
# log_level = "WARNING"      # DEBUG | INFO | WARNING | ERROR | CRITICAL (CLI --log-level takes precedence)
# binary_arrays = false      # Encode numpy arrays as base64 binary in JSON output (CLI --binary-arrays takes precedence)
# on_imas_error = "fallback-json"  # What to do when an IDS fails to write: "fallback-json" | "raise"

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
