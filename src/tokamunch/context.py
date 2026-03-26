from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import tokamunch as tm


@dataclass
class CLIContext:
    cfg: Any
    mapper: Any
    tokamap: tm.TokamapInterface
    device: str
    shot: int
    config_path: str

    def ids_helper(self, ids_name: str) -> tm.IDSHelper:
        return tm.IDSHelper.from_ids_name(ids_name)


def load_context(config: str, device: str | None, shot: int | None) -> CLIContext:
    cfg = tm.load_cli_config(config)
    mapper = tm.create_mapper_from_config(cfg)

    resolved_device = device or cfg.mapper.device
    resolved_shot = shot if shot is not None else cfg.run.default_shot

    tokamap = tm.TokamapInterface(
        mapper,
        resolved_device,
        {"shot": resolved_shot},
    )

    return CLIContext(
        cfg=cfg,
        mapper=mapper,
        tokamap=tokamap,
        device=resolved_device,
        shot=resolved_shot,
        config_path=config,
    )
