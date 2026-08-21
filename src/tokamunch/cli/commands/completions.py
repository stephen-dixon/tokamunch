"""munchi completions — generate shell completion scripts."""

from __future__ import annotations

import argparse


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = subparsers.add_parser(
        "completions",
        help="Generate shell completion scripts",
    )
    parser.add_argument(
        "shell",
        choices=["bash", "zsh", "fish"],
        help="Target shell",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from ...completions import (
        generate_bash_completion,
        generate_fish_completion,
        generate_zsh_completion,
        get_ids_names,
    )

    ids_names = get_ids_names()

    if args.shell == "bash":
        print(generate_bash_completion(ids_names), end="")
    elif args.shell == "zsh":
        print(generate_zsh_completion(ids_names), end="")
    elif args.shell == "fish":
        print(generate_fish_completion(ids_names), end="")
    else:
        raise ValueError(f"Unknown shell {args.shell!r}")

    return 0
