# tokamunch

![Logo](./docs/logo.png)

Python library and CLI (`munchi`) for generating [IMAS IDS](https://imas.iter.org/) mappings using [libtokamap](https://git.iter.org/projects/IMAS/repos/libtokamap).  Given a device name and a set of IDS names, tokamunch expands the IDS schema, calls your mapper for every concrete path, and writes results as JSON, HDF5, or NetCDF.

This is mostly vibes and slop for now.

---

## Installation

```bash
pip install tokamunch                   # core (JSON output only)
pip install "tokamunch[imas]"           # adds HDF5 / NetCDF output via imas-python
pip install "tokamunch[dev]"            # adds test + lint tools
```

---

## Quickstart

```bash
# 1. Scaffold a config file for your device.
munchi init-config --output munchi.toml
# Edit munchi.toml: set mapper.device and point to your libtokamap config.

# 2. Preview the paths that will be mapped.
munchi paths --ids magnetics

# 3. Run the mapping and write results.
munchi map --ids magnetics --output results.json

# 4. Inspect the output.
munchi diff results-prev.json results.json
```

---

## Mapping development workflow

```bash
# 1. Generate a mapping template with annotated stubs.
munchi init-mapping --ids magnetics --leaves-only --output magnetics.json

# 2. Edit magnetics.json: replace {"comment": ""} stubs with real mapper paths.

# 3. Map only the paths defined in your file.
munchi map --ids magnetics --mapping magnetics.json --output results.json

# 4. Check your output against a previous run.
munchi diff baseline.json results.json

# 5. Schema updated? Add stubs for new paths without touching existing entries.
munchi update-mapping --ids magnetics --mapping magnetics.json \
    --output magnetics-updated.json

# 6. Incrementally fill in newly mapped paths from an existing result file.
munchi update --input results.json --output results-full.json \
    --ids magnetics --mapping magnetics-updated.json

# 7. Generate shell completions (paste into your shell rc).
munchi completions bash >> ~/.bash_completion
munchi completions zsh  >> ~/.zshrc
munchi completions fish > ~/.config/fish/completions/munchi.fish
```

---

## Commands

| Command | Description |
|---|---|
| `munchi paths` | List all concrete IDS paths that would be mapped |
| `munchi map` | Run the mapping and write output |
| `munchi init-config` | Generate a skeleton `munchi.toml` |
| `munchi init-mapping` | Generate a mapping template JSON with annotation stubs |
| `munchi update-mapping` | Add stubs for missing paths to an existing mapping file |
| `munchi update` | Map missing paths from an existing result file |
| `munchi diff` | Compare two result files (JSON or IMAS) |
| `munchi convert` | Convert between JSON and IMAS file formats |
| `munchi check` | Validate configuration and mapper connectivity |
| `munchi completions` | Print shell completion scripts |

### Key flags for `munchi map`

| Flag | Description |
|---|---|
| `--ids NAME [NAME ...]` | IDS names to process |
| `--mapping FILE` | Restrict paths to keys in a mapping file |
| `--output FILE` | Output file (`.json`, `.h5`, `.nc`) |
| `--leaves-only` | Only expand leaf (scalar) paths |
| `--shots N [N ...]` | Map multiple shots; use `{shot}` in output filename |
| `--shot-range START END` | Map a range of shots |
| `--checkpoint FILE` | Resume an interrupted run from a checkpoint |
| `--dry-run` | Expand paths but skip all mapper calls |
| `--limit N` | Process at most N paths |
| `--verbose` | Show full values and error tracebacks |
| `--set KEY=VALUE` | Override config values inline (repeatable) |
| `--profile-stats` | Print a timing and call-count summary after the run |
| `--profile FILE` | Write a `cProfile` stats file (view with `snakeviz`) |

---

## Configuration

```toml
# munchi.toml

[mapper]
device = "mast"

# Option A — point to a libtokamap config file.
config = "config.toml"

# Option B — supply libtokamap config inline.
# [mapper.config_params]
# mapping_directory = "/path/to/mappings"
# schemas_directory = "/path/to/schemas"

[run]
default_shot = 30420
log_level = "WARNING"      # DEBUG | INFO | WARNING | ERROR | CRITICAL
binary_arrays = false      # base64-encode numpy arrays in JSON output
on_imas_error = "fallback-json"  # "fallback-json" | "raise"

[run.concurrency]
mode = "process"   # "serial" | "thread" | "process"
workers = 8
```

Override any `run.*` or `mapper.*` key on the command line without editing the file:

```bash
munchi map --ids magnetics --set run.concurrency.mode=thread \
    --set run.concurrency.workers=4 --output results.json
```

---

## Multi-shot mapping

```bash
# Map shots 47125 and 47130; output goes to results_47125.json and results_47130.json.
munchi map --ids magnetics --shots 47125 47130 --output "results_{shot}.json"

# Map every shot from 47100 to 47200.
munchi map --ids magnetics --shot-range 47100 47200 --output "results_{shot}.json"
```

---

## Library usage

```python
from tokamunch import MappingContext, TokamapInterface
from tokamunch.mapping import collect_mapped_values
from tokamunch.outputs import write_json_file

# Build a context programmatically (no config file required).
ctx = MappingContext.from_config("munchi.toml", shot=47125)

# Run the mapping.
records, summary = collect_mapped_values(ctx, ids_name="magnetics")
write_json_file("results.json", records)
print(summary)
```

### JSON → IDS objects (in-memory augment + write)

```python
from tokamunch.convert import read_json_records, records_to_ids_objects
from tokamunch.write_ids import write_imas_output

records = read_json_records("results.json")
# Augment with manually constructed MappingRecords here if needed.
write_imas_output("output.nc", records=records, force=True)
```

### Comparing results programmatically

```python
from tokamunch.diff import diff_files, render_diff

entries = diff_files("baseline.json", "updated.json", ids_names=["magnetics"])
print(render_diff(entries, "baseline", "updated", show_unchanged=False))
```

---

## Shell completions

```bash
# bash
munchi completions bash >> ~/.bash_completion
# (add `. ~/.bash_completion` to ~/.bashrc if not already sourced)

# zsh
munchi completions zsh >> ~/.zshrc

# fish
munchi completions fish > ~/.config/fish/completions/munchi.fish
```

---

## Development

```bash
pip install -e ".[dev]"
pytest                  # run all tests
ruff check src tests    # lint
ruff format src tests   # format
mypy src                # type-check
```
