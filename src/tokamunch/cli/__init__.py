"""CLI package for the munchi command.

Entry point: ``tokamunch.cli.main:main`` (configured in pyproject.toml).

Where to make changes:
- Add/modify arguments for a command: ``cli/commands/<command>.py``
- Add a new command: create ``cli/commands/<name>.py`` and register it in ``cli/parser.py``
- Shared argument helpers: ``cli/parser.py``
- Shared runtime helpers (config loading, context creation): ``cli/common.py``
- Logging setup and top-level error handling: ``cli/main.py``
"""

from .main import main
from .parser import build_parser

__all__ = ["build_parser", "main"]
