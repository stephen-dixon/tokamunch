"""CLI package for the munchi command.

Entry point: ``tokamunch.cli.main:main`` (configured in pyproject.toml).

Where to make changes:
- Add/modify arguments for a command: ``cli/commands/<command>.py``
- Add a new command: create ``cli/commands/<name>.py`` and register it in ``cli/parser.py``
- Shared argument helpers: ``cli/parser.py``
- Shared runtime helpers (config loading, context creation): ``cli/common.py``
- Logging setup and top-level error handling: ``cli/main.py``
"""

from .commands import check as _check
from .commands import completions as _completions
from .commands import convert as _convert
from .commands import diff as _diff
from .commands import init as _init
from .commands import map as _map
from .commands import paths as _paths
from .commands import update as _update
from .main import main
from .parser import (
    PATH_SYNTAX_EPILOG,
    add_common_arguments,
    add_force_argument,
    add_ids_or_path_arguments,
    add_match_argument,
    add_verbose_errors_argument,
    build_parser,
)

# Backward-compatibility aliases for the pre-package tokamunch.cli module.
# Canonical location is tokamunch.cli.commands.<command>.
cmd_check = _check.run
cmd_completions = _completions.run
cmd_convert = _convert.run
cmd_diff = _diff.run
cmd_init_config = _init.run_init_config
cmd_init_mapping = _init.run_init_mapping
cmd_map = _map.run
cmd_paths = _paths.run
cmd_update = _update.run_update
cmd_update_mapping = _update.run_update_mapping

__all__ = [
    "PATH_SYNTAX_EPILOG",
    "add_common_arguments",
    "add_force_argument",
    "add_ids_or_path_arguments",
    "add_match_argument",
    "add_verbose_errors_argument",
    "build_parser",
    "cmd_check",
    "cmd_completions",
    "cmd_convert",
    "cmd_diff",
    "cmd_init_config",
    "cmd_init_mapping",
    "cmd_map",
    "cmd_paths",
    "cmd_update",
    "cmd_update_mapping",
    "main",
]
