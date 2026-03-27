from __future__ import annotations

from importlib.metadata import entry_points

from .plugin_api import DataSourceFactory


def load_data_source_factory(name: str) -> DataSourceFactory:
    eps = entry_points(group="tokamunch.data_sources")
    matches = [ep for ep in eps if ep.name == name]

    if not matches:
        available = ", ".join(sorted(ep.name for ep in eps)) or "<none>"
        raise ValueError(
            f"No data-source plugin named {name!r} found. "
            f"Available plugins: {available}"
        )

    if len(matches) > 1:
        raise ValueError(f"Multiple data-source plugins named {name!r} found")

    factory: DataSourceFactory = matches[0].load()
    return factory
