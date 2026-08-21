from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataSourceMetadata:
    """Metadata describing a tokamunch data-source plugin.

    Returned alongside the factory when loading a plugin.  Plugin authors
    should define a module-level ``PLUGIN_METADATA`` instance; if absent a
    safe default is synthesised at load time.
    """

    name: str
    display_name: str | None = None
    version: str | None = None
    description: str = ""

    # Execution safety
    thread_safe: bool = False
    process_safe: bool = True
    reentrant: bool = False

    # Behaviour
    deterministic: bool = True
    cacheable: bool = False

    # Operational hints
    requires_network: bool = False
    requires_auth: bool = False
