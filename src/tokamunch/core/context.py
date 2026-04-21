from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..ids.helper import IDSHelper
from ..mapping.data_source import TokamapInterface
from ..mapping.mapper_factory import create_mapper_from_config
from .config import CLIConfig, ConcurrencyConfig, load_cli_config


@dataclass
class MappingContext:
    """Holds all runtime state needed to execute a mapping run.

    Can be constructed directly for programmatic (library) use, or via
    ``from_config`` to load settings from a TOML config file for CLI use.

    ``cli_config`` is required for process-based concurrency: each worker
    process receives the full ``CLIConfig`` and reconstructs its own mapper
    without needing any config file to be present on disk.
    """

    mapper: Any
    tokamap: TokamapInterface
    device: str
    shot: int | None
    # None when constructed programmatically without a config file.
    cli_config: CLIConfig | None = None
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)

    def ids_helper(self, ids_name: str) -> IDSHelper:
        return IDSHelper.from_ids_name(ids_name)

    @classmethod
    def from_config(
        cls,
        config: str,
        *,
        device: str | None = None,
        shot: int | None = None,
    ) -> MappingContext:
        """Build a MappingContext from a munchi TOML config file.

        ``device`` and ``shot`` override the values in the config when provided.
        """
        cfg = load_cli_config(config)
        mapper = create_mapper_from_config(cfg)

        resolved_device = device or cfg.mapper.device
        resolved_shot = shot if shot is not None else cfg.run.default_shot

        tokamap = TokamapInterface(mapper, resolved_device, shot=resolved_shot)

        return cls(
            mapper=mapper,
            tokamap=tokamap,
            device=resolved_device,
            shot=resolved_shot,
            cli_config=cfg,
            concurrency=cfg.run.concurrency,
        )
