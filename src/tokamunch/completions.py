"""Shell completion script generation for the munchi CLI."""

from __future__ import annotations


def get_ids_names() -> list[str]:
    """Return sorted list of known IDS names from imas_data_dictionary.

    Returns an empty list if the data dictionary is not available.
    """
    try:
        from imas_data_dictionary import IDSInfo

        return sorted(IDSInfo().ids_names)
    except Exception:
        return []


def generate_bash_completion(ids_names: list[str]) -> str:
    """Generate a bash completion script for munchi."""
    ids_list = " ".join(ids_names)
    return f"""\
# munchi bash completion
# Source this file or add to ~/.bashrc:
#   source <(munchi completions bash)

_munchi_complete() {{
    local cur prev words cword
    _init_completion || return

    local subcommands="paths map convert init-config init-mapping check update-mapping update diff completions"
    local ids_names="{ids_list}"

    # Subcommand completion
    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$subcommands" -- "$cur") )
        return
    fi

    local subcmd="${{words[1]}}"

    # --ids completion
    if [[ "$prev" == "--ids" ]]; then
        COMPREPLY=( $(compgen -W "$ids_names" -- "$cur") )
        return
    fi

    # Flag completion based on subcommand
    case "$subcmd" in
        paths)
            local flags="--config --device --shot --leaves-only --match --schema-map --output --force --ids"
            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            ;;
        map)
            local flags="--config --device --shot --leaves-only --ids --path --paths --match --force --verbose-errors --verbose --output --mapping --concurrency-mode --workers --binary-arrays --on-imas-error --dry-run --limit --profile-stats --profile --shots --shot-range --checkpoint --set"
            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            ;;
        convert)
            local flags="--input --output --ids --binary-arrays --on-imas-error --force"
            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            ;;
        init-config)
            local flags="--output --force"
            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            ;;
        init-mapping)
            local flags="--ids --output --leaves-only --force"
            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            ;;
        check)
            local flags="--config --device --shot --leaves-only --ids"
            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            ;;
        update-mapping)
            local flags="--ids --mapping --output --leaves-only --force"
            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            ;;
        update)
            local flags="--input --output --ids --mapping --config --device --shot --force"
            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            ;;
        diff)
            local flags="--ids --show-unchanged"
            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            ;;
        completions)
            local shells="bash zsh fish"
            COMPREPLY=( $(compgen -W "$shells" -- "$cur") )
            ;;
    esac
}}

complete -F _munchi_complete munchi
"""


def generate_zsh_completion(ids_names: list[str]) -> str:
    """Generate a zsh completion script for munchi."""
    ids_spec = " ".join(f"'{n}'" for n in ids_names)
    return f"""\
#compdef munchi
# munchi zsh completion
# Add to ~/.zshrc:
#   source <(munchi completions zsh)
# or copy to a directory in your $fpath.

_munchi() {{
    local -a subcommands
    subcommands=(
        'paths:Expand and print concrete IDS runtime paths'
        'map:Map one concrete path or all concrete paths of an IDS'
        'convert:Convert data between supported file formats'
        'init-config:Create a skeleton munchi config file'
        'init-mapping:Create a blank JSON mapping template'
        'check:Validate config/mapper setup and optionally an IDS schema'
        'update-mapping:Update an existing mapping file with new stubs'
        'update:Map missing paths and merge with existing results'
        'diff:Compare two mapping result files'
        'completions:Generate shell completion scripts'
    )

    local -a ids_names
    ids_names=({ids_spec})

    local -a common_flags
    common_flags=(
        '--config[munchi config file]:config file:_files'
        '--device[Override device]:device'
        '--shot[Override shot]:shot'
        '--leaves-only[Only include leaf paths]'
    )

    if (( CURRENT == 2 )); then
        _describe 'subcommand' subcommands
        return
    fi

    case $words[2] in
        paths)
            _arguments $common_flags \\
                '--ids[IDS name]:ids:($ids_names)' \\
                '--match[Glob filter]:pattern' \\
                '--schema-map[Show schema map]' \\
                '--output[Output file]:file:_files' \\
                '--force[Overwrite existing file]'
            ;;
        map)
            _arguments $common_flags \\
                '--ids[IDS name]:ids:($ids_names)' \\
                '--path[Single concrete path]:path' \\
                '--paths[Multiple concrete paths]:paths' \\
                '--match[Glob filter]:pattern' \\
                '--force[Overwrite existing file]' \\
                '--verbose-errors[Show suppressed errors]' \\
                '--verbose[Verbose output with value details]' \\
                '--output[Output file]:file:_files' \\
                '--mapping[Mapping file]:file:_files' \\
                '--concurrency-mode[Concurrency mode]:mode:(serial thread process)' \\
                '--workers[Number of workers]:n' \\
                '--binary-arrays[Encode arrays as base64]' \\
                '--on-imas-error[Error handling]:mode:(fallback-json raise)' \\
                '--dry-run[Expand paths only]' \\
                '--limit[Map at most N paths]:n' \\
                '--shots[Specific shot numbers]:shots' \\
                '--shot-range[Shot range START END STEP]:range' \\
                '--checkpoint[Checkpoint file]:file:_files' \\
                '--set[Config override KEY=VALUE]:override'
            ;;
        convert)
            _arguments \\
                '--input[Input file]:file:_files' \\
                '--output[Output file]:file:_files' \\
                '--ids[IDS names]:ids:($ids_names)' \\
                '--binary-arrays[Encode arrays as base64]' \\
                '--on-imas-error[Error handling]:mode:(fallback-json raise)' \\
                '--force[Overwrite existing file]'
            ;;
        init-config)
            _arguments \\
                '--output[Output file]:file:_files' \\
                '--force[Overwrite existing file]'
            ;;
        init-mapping)
            _arguments \\
                '--ids[IDS name]:ids:($ids_names)' \\
                '--output[Output file]:file:_files' \\
                '--leaves-only[Only include leaf paths]' \\
                '--force[Overwrite existing file]'
            ;;
        check)
            _arguments $common_flags \\
                '--ids[IDS name]:ids:($ids_names)'
            ;;
        update-mapping)
            _arguments \\
                '--ids[IDS name]:ids:($ids_names)' \\
                '--mapping[Existing mapping file]:file:_files' \\
                '--output[Output file]:file:_files' \\
                '--leaves-only[Only include leaf paths]' \\
                '--force[Overwrite existing file]'
            ;;
        update)
            _arguments $common_flags \\
                '--input[Existing result file]:file:_files' \\
                '--output[Output file]:file:_files' \\
                '--ids[IDS name]:ids:($ids_names)' \\
                '--mapping[Mapping file]:file:_files' \\
                '--force[Overwrite existing file]'
            ;;
        diff)
            _arguments \\
                '--ids[IDS names]:ids:($ids_names)' \\
                '--show-unchanged[Show unchanged paths]'
            ;;
        completions)
            _arguments ':shell:(bash zsh fish)'
            ;;
    esac
}}

_munchi "$@"
"""


def generate_fish_completion(ids_names: list[str]) -> str:
    """Generate a fish shell completion script for munchi."""
    ids_completions = "\n".join(
        f"complete -c munchi -n '__fish_seen_subcommand_from paths map init-mapping check update-mapping update diff' -l ids -a '{name}' -d 'IDS: {name}'"
        for name in ids_names
    )
    return f"""\
# munchi fish completion
# Source this file or add to ~/.config/fish/completions/munchi.fish

# Subcommands
set -l subcommands paths map convert init-config init-mapping check update-mapping update diff completions

complete -c munchi -f -n 'not __fish_seen_subcommand_from $subcommands' -a paths -d 'Expand and print concrete IDS runtime paths'
complete -c munchi -f -n 'not __fish_seen_subcommand_from $subcommands' -a map -d 'Map one concrete path or all concrete paths of an IDS'
complete -c munchi -f -n 'not __fish_seen_subcommand_from $subcommands' -a convert -d 'Convert data between supported file formats'
complete -c munchi -f -n 'not __fish_seen_subcommand_from $subcommands' -a init-config -d 'Create a skeleton munchi config file'
complete -c munchi -f -n 'not __fish_seen_subcommand_from $subcommands' -a init-mapping -d 'Create a blank JSON mapping template'
complete -c munchi -f -n 'not __fish_seen_subcommand_from $subcommands' -a check -d 'Validate config/mapper setup'
complete -c munchi -f -n 'not __fish_seen_subcommand_from $subcommands' -a update-mapping -d 'Update an existing mapping file with new stubs'
complete -c munchi -f -n 'not __fish_seen_subcommand_from $subcommands' -a update -d 'Map missing paths and merge with existing results'
complete -c munchi -f -n 'not __fish_seen_subcommand_from $subcommands' -a diff -d 'Compare two mapping result files'
complete -c munchi -f -n 'not __fish_seen_subcommand_from $subcommands' -a completions -d 'Generate shell completion scripts'

# Common flags
complete -c munchi -n '__fish_seen_subcommand_from paths map check' -l config -d 'munchi config file' -r
complete -c munchi -n '__fish_seen_subcommand_from paths map check' -l device -d 'Override device' -r
complete -c munchi -n '__fish_seen_subcommand_from paths map check' -l shot -d 'Override shot' -r
complete -c munchi -n '__fish_seen_subcommand_from paths map check' -l leaves-only -d 'Only include leaf paths'

# IDS name completions
{ids_completions}

# map-specific flags
complete -c munchi -n '__fish_seen_subcommand_from map' -l path -d 'Single concrete path' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l paths -d 'Multiple concrete paths' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l match -d 'Glob filter' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l force -d 'Overwrite existing file'
complete -c munchi -n '__fish_seen_subcommand_from map' -l verbose-errors -d 'Show suppressed errors'
complete -c munchi -n '__fish_seen_subcommand_from map' -l verbose -d 'Verbose output'
complete -c munchi -n '__fish_seen_subcommand_from map' -l output -d 'Output file' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l mapping -d 'Mapping file' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l concurrency-mode -d 'Concurrency mode' -a 'serial thread process' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l workers -d 'Number of workers' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l binary-arrays -d 'Encode arrays as base64'
complete -c munchi -n '__fish_seen_subcommand_from map' -l on-imas-error -d 'Error handling' -a 'fallback-json raise' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l dry-run -d 'Expand paths only'
complete -c munchi -n '__fish_seen_subcommand_from map' -l limit -d 'Map at most N paths' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l shots -d 'Specific shot numbers' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l shot-range -d 'Shot range' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l checkpoint -d 'Checkpoint file' -r
complete -c munchi -n '__fish_seen_subcommand_from map' -l set -d 'Config override KEY=VALUE' -r

# completions subcommand
complete -c munchi -n '__fish_seen_subcommand_from completions' -a 'bash zsh fish' -d 'Shell'
"""
