import json
import pytest
from pathlib import Path

from tokamunch.config import (
    CLIConfig,
    ConcurrencyConfig,
    ConcurrencyMode,
    DataSourceConfig,
    MapperConfig,
    RunConfig,
    load_cli_config,
)


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestLoadCliConfigFileRef:
    def test_loads_config_file_path(self, tmp_path: Path) -> None:
        mapper_cfg = tmp_path / "config.toml"
        mapper_cfg.write_text("[settings]\n", encoding="utf-8")

        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(munchi_cfg, f"""
[mapper]
device = "mast"
config = "{mapper_cfg}"
""")
        cfg = load_cli_config(munchi_cfg)
        assert cfg.mapper.device == "mast"
        assert cfg.mapper.config == str(mapper_cfg)
        assert cfg.mapper.config_params is None

    def test_missing_config_file_raises(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(munchi_cfg, """
[mapper]
device = "mast"
config = "/nonexistent/config.toml"
""")
        with pytest.raises(FileNotFoundError, match="Mapper config file not found"):
            load_cli_config(munchi_cfg)


class TestLoadCliConfigInlineParams:
    def test_loads_config_params(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(munchi_cfg, """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/mappings"
schemas_directory = "/schemas"
""")
        cfg = load_cli_config(munchi_cfg)
        assert cfg.mapper.config is None
        assert cfg.mapper.config_params == {
            "mapping_directory": "/mappings",
            "schemas_directory": "/schemas",
        }

    def test_extra_params_preserved(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(munchi_cfg, """
[mapper]
device = "iter"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"
trace = false
cache = true
""")
        cfg = load_cli_config(munchi_cfg)
        assert cfg.mapper.config_params["trace"] is False
        assert cfg.mapper.config_params["cache"] is True


class TestLoadCliConfigValidation:
    def test_both_config_and_params_raises(self, tmp_path: Path) -> None:
        mapper_cfg = tmp_path / "config.toml"
        mapper_cfg.write_text("", encoding="utf-8")

        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(munchi_cfg, f"""
[mapper]
device = "mast"
config = "{mapper_cfg}"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"
""")
        with pytest.raises(ValueError, match="mutually exclusive"):
            load_cli_config(munchi_cfg)

    def test_neither_config_nor_params_raises(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(munchi_cfg, """
[mapper]
device = "mast"
""")
        with pytest.raises(ValueError, match="One of"):
            load_cli_config(munchi_cfg)


class TestLoadCliConfigConcurrency:
    def test_default_concurrency_is_serial(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(munchi_cfg, """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"
""")
        cfg = load_cli_config(munchi_cfg)
        assert cfg.run.concurrency.mode == ConcurrencyMode.SERIAL
        assert cfg.run.concurrency.workers == 1

    def test_process_concurrency_parsed(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(munchi_cfg, """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"

[run.concurrency]
mode = "process"
workers = 8
""")
        cfg = load_cli_config(munchi_cfg)
        assert cfg.run.concurrency.mode == ConcurrencyMode.PROCESS
        assert cfg.run.concurrency.workers == 8


class TestLoadCliConfigDataSources:
    def test_data_sources_parsed(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(munchi_cfg, """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"

[data_sources.pyuda]
plugin = "pyuda"
enabled = true
args = { host = "localhost", port = 56565 }
""")
        cfg = load_cli_config(munchi_cfg)
        assert len(cfg.data_sources) == 1
        ds = cfg.data_sources[0]
        assert ds.mapper_name == "pyuda"
        assert ds.plugin == "pyuda"
        assert ds.enabled is True
        assert ds.args == {"host": "localhost", "port": 56565}

    def test_disabled_data_source(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(munchi_cfg, """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"

[data_sources.pyuda]
plugin = "pyuda"
enabled = false
""")
        cfg = load_cli_config(munchi_cfg)
        assert cfg.data_sources[0].enabled is False
