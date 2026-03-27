from pathlib import Path

import pytest

from tokamunch.config import (
    CLIConfig,
    ConcurrencyConfig,
    ConcurrencyMode,
    MapperConfig,
    RunConfig,
    apply_config_overrides,
    load_cli_config,
)


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestLoadCliConfigFileRef:
    def test_loads_config_file_path(self, tmp_path: Path) -> None:
        mapper_cfg = tmp_path / "config.toml"
        mapper_cfg.write_text("[settings]\n", encoding="utf-8")

        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(
            munchi_cfg,
            f"""
[mapper]
device = "mast"
config = "{mapper_cfg}"
""",
        )
        cfg = load_cli_config(munchi_cfg)
        assert cfg.mapper.device == "mast"
        assert cfg.mapper.config == str(mapper_cfg)
        assert cfg.mapper.config_params is None

    def test_missing_config_file_raises(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(
            munchi_cfg,
            """
[mapper]
device = "mast"
config = "/nonexistent/config.toml"
""",
        )
        with pytest.raises(FileNotFoundError, match="Mapper config file not found"):
            load_cli_config(munchi_cfg)


class TestLoadCliConfigInlineParams:
    def test_loads_config_params(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(
            munchi_cfg,
            """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/mappings"
schemas_directory = "/schemas"
""",
        )
        cfg = load_cli_config(munchi_cfg)
        assert cfg.mapper.config is None
        assert cfg.mapper.config_params == {
            "mapping_directory": "/mappings",
            "schemas_directory": "/schemas",
        }

    def test_extra_params_preserved(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(
            munchi_cfg,
            """
[mapper]
device = "iter"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"
trace = false
cache = true
""",
        )
        cfg = load_cli_config(munchi_cfg)
        assert cfg.mapper.config_params["trace"] is False
        assert cfg.mapper.config_params["cache"] is True


class TestLoadCliConfigValidation:
    def test_both_config_and_params_raises(self, tmp_path: Path) -> None:
        mapper_cfg = tmp_path / "config.toml"
        mapper_cfg.write_text("", encoding="utf-8")

        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(
            munchi_cfg,
            f"""
[mapper]
device = "mast"
config = "{mapper_cfg}"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"
""",
        )
        with pytest.raises(ValueError, match="mutually exclusive"):
            load_cli_config(munchi_cfg)

    def test_neither_config_nor_params_raises(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(
            munchi_cfg,
            """
[mapper]
device = "mast"
""",
        )
        with pytest.raises(ValueError, match="One of"):
            load_cli_config(munchi_cfg)


class TestLoadCliConfigConcurrency:
    def test_default_concurrency_is_serial(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(
            munchi_cfg,
            """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"
""",
        )
        cfg = load_cli_config(munchi_cfg)
        assert cfg.run.concurrency.mode == ConcurrencyMode.SERIAL
        assert cfg.run.concurrency.workers == 1

    def test_process_concurrency_parsed(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(
            munchi_cfg,
            """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"

[run.concurrency]
mode = "process"
workers = 8
""",
        )
        cfg = load_cli_config(munchi_cfg)
        assert cfg.run.concurrency.mode == ConcurrencyMode.PROCESS
        assert cfg.run.concurrency.workers == 8


class TestLoadCliConfigLogLevel:
    _BASE = """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"
"""

    def test_default_log_level_is_warning(self, tmp_path: Path) -> None:
        p = tmp_path / "munchi.toml"
        _write_toml(p, self._BASE)
        cfg = load_cli_config(p)
        assert cfg.run.log_level == "WARNING"

    def test_log_level_parsed(self, tmp_path: Path) -> None:
        p = tmp_path / "munchi.toml"
        _write_toml(p, self._BASE + '\n[run]\nlog_level = "DEBUG"\n')
        cfg = load_cli_config(p)
        assert cfg.run.log_level == "DEBUG"

    def test_log_level_case_insensitive(self, tmp_path: Path) -> None:
        p = tmp_path / "munchi.toml"
        _write_toml(p, self._BASE + '\n[run]\nlog_level = "info"\n')
        cfg = load_cli_config(p)
        assert cfg.run.log_level == "INFO"

    def test_invalid_log_level_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "munchi.toml"
        _write_toml(p, self._BASE + '\n[run]\nlog_level = "VERBOSE"\n')
        with pytest.raises(ValueError, match="log_level"):
            load_cli_config(p)


class TestLoadCliConfigBinaryArrays:
    _BASE = """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"
"""

    def test_default_binary_arrays_is_false(self, tmp_path: Path) -> None:
        p = tmp_path / "munchi.toml"
        _write_toml(p, self._BASE)
        cfg = load_cli_config(p)
        assert cfg.run.binary_arrays is False

    def test_binary_arrays_true_parsed(self, tmp_path: Path) -> None:
        p = tmp_path / "munchi.toml"
        _write_toml(p, self._BASE + "\n[run]\nbinary_arrays = true\n")
        cfg = load_cli_config(p)
        assert cfg.run.binary_arrays is True


class TestLoadCliConfigOnImasError:
    _BASE = """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"
"""

    def test_default_on_imas_error_is_fallback_json(self, tmp_path: Path) -> None:
        p = tmp_path / "munchi.toml"
        _write_toml(p, self._BASE)
        cfg = load_cli_config(p)
        assert cfg.run.on_imas_error == "fallback-json"

    def test_raise_mode_parsed(self, tmp_path: Path) -> None:
        p = tmp_path / "munchi.toml"
        _write_toml(p, self._BASE + '\n[run]\non_imas_error = "raise"\n')
        cfg = load_cli_config(p)
        assert cfg.run.on_imas_error == "raise"

    def test_invalid_on_imas_error_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "munchi.toml"
        _write_toml(p, self._BASE + '\n[run]\non_imas_error = "ignore"\n')
        with pytest.raises(ValueError, match="on_imas_error"):
            load_cli_config(p)


class TestLoadCliConfigDataSources:
    def test_data_sources_parsed(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(
            munchi_cfg,
            """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"

[data_sources.pyuda]
plugin = "pyuda"
enabled = true
args = { host = "localhost", port = 56565 }
""",
        )
        cfg = load_cli_config(munchi_cfg)
        assert len(cfg.data_sources) == 1
        ds = cfg.data_sources[0]
        assert ds.mapper_name == "pyuda"
        assert ds.plugin == "pyuda"
        assert ds.enabled is True
        assert ds.args == {"host": "localhost", "port": 56565}

    def test_disabled_data_source(self, tmp_path: Path) -> None:
        munchi_cfg = tmp_path / "munchi.toml"
        _write_toml(
            munchi_cfg,
            """
[mapper]
device = "mast"

[mapper.config_params]
mapping_directory = "/m"
schemas_directory = "/s"

[data_sources.pyuda]
plugin = "pyuda"
enabled = false
""",
        )
        cfg = load_cli_config(munchi_cfg)
        assert cfg.data_sources[0].enabled is False


# ── apply_config_overrides ────────────────────────────────────────────────────


def _base_cfg() -> CLIConfig:
    """Minimal valid CLIConfig for override tests (no file I/O needed)."""
    return CLIConfig(
        mapper=MapperConfig(
            device="mast",
            config_params={"mapping_directory": "/m", "schemas_directory": "/s"},
        ),
        run=RunConfig(),
        data_sources=[],
    )


class TestApplyConfigOverrides:
    def test_empty_overrides_returns_equivalent_config(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, [])
        assert result.mapper.device == cfg.mapper.device
        assert result.run.log_level == cfg.run.log_level

    def test_override_mapper_device(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["mapper.device=jet"])
        assert result.mapper.device == "jet"

    def test_override_run_concurrency_mode_thread(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["run.concurrency.mode=thread"])
        assert result.run.concurrency.mode == ConcurrencyMode.THREAD

    def test_override_run_concurrency_mode_process(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["run.concurrency.mode=process"])
        assert result.run.concurrency.mode == ConcurrencyMode.PROCESS

    def test_override_run_concurrency_workers(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["run.concurrency.workers=8"])
        assert result.run.concurrency.workers == 8

    def test_override_run_log_level(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["run.log_level=DEBUG"])
        assert result.run.log_level == "DEBUG"

    def test_override_run_log_level_case_insensitive(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["run.log_level=info"])
        assert result.run.log_level == "INFO"

    def test_override_run_binary_arrays_true(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["run.binary_arrays=true"])
        assert result.run.binary_arrays is True

    def test_override_run_binary_arrays_false(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["run.binary_arrays=false"])
        assert result.run.binary_arrays is False

    def test_override_run_binary_arrays_numeric(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["run.binary_arrays=1"])
        assert result.run.binary_arrays is True

    def test_override_run_on_imas_error_raise(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["run.on_imas_error=raise"])
        assert result.run.on_imas_error == "raise"

    def test_override_run_on_imas_error_fallback_json(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["run.on_imas_error=fallback-json"])
        assert result.run.on_imas_error == "fallback-json"

    def test_override_run_default_shot(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(cfg, ["run.default_shot=47125"])
        assert result.run.default_shot == 47125

    def test_multiple_overrides_combined(self) -> None:
        cfg = _base_cfg()
        result = apply_config_overrides(
            cfg,
            [
                "mapper.device=iter",
                "run.concurrency.mode=process",
                "run.concurrency.workers=4",
                "run.log_level=DEBUG",
            ],
        )
        assert result.mapper.device == "iter"
        assert result.run.concurrency.mode == ConcurrencyMode.PROCESS
        assert result.run.concurrency.workers == 4
        assert result.run.log_level == "DEBUG"

    def test_original_config_not_mutated(self) -> None:
        cfg = _base_cfg()
        apply_config_overrides(cfg, ["mapper.device=iter"])
        assert cfg.mapper.device == "mast"

    def test_data_sources_preserved(self) -> None:
        from tokamunch.config import DataSourceConfig

        cfg = _base_cfg()
        cfg = CLIConfig(
            mapper=cfg.mapper,
            run=cfg.run,
            data_sources=[DataSourceConfig(mapper_name="pyuda", plugin="pyuda")],
        )
        result = apply_config_overrides(cfg, ["mapper.device=iter"])
        assert len(result.data_sources) == 1
        assert result.data_sources[0].mapper_name == "pyuda"

    def test_invalid_key_raises(self) -> None:
        cfg = _base_cfg()
        with pytest.raises(ValueError, match="Unknown config override key"):
            apply_config_overrides(cfg, ["run.unknown_key=foo"])

    def test_missing_equals_raises(self) -> None:
        cfg = _base_cfg()
        with pytest.raises(ValueError, match="KEY=VALUE"):
            apply_config_overrides(cfg, ["run.log_level"])

    def test_invalid_concurrency_mode_raises(self) -> None:
        cfg = _base_cfg()
        with pytest.raises(ValueError, match="run.concurrency.mode"):
            apply_config_overrides(cfg, ["run.concurrency.mode=parallel"])

    def test_invalid_concurrency_workers_raises(self) -> None:
        cfg = _base_cfg()
        with pytest.raises(ValueError, match="run.concurrency.workers"):
            apply_config_overrides(cfg, ["run.concurrency.workers=many"])

    def test_invalid_log_level_raises(self) -> None:
        cfg = _base_cfg()
        with pytest.raises(ValueError, match="run.log_level"):
            apply_config_overrides(cfg, ["run.log_level=VERBOSE"])

    def test_invalid_binary_arrays_raises(self) -> None:
        cfg = _base_cfg()
        with pytest.raises(ValueError, match="true/false"):
            apply_config_overrides(cfg, ["run.binary_arrays=yes"])

    def test_invalid_on_imas_error_raises(self) -> None:
        cfg = _base_cfg()
        with pytest.raises(ValueError, match="run.on_imas_error"):
            apply_config_overrides(cfg, ["run.on_imas_error=ignore"])

    def test_invalid_default_shot_raises(self) -> None:
        cfg = _base_cfg()
        with pytest.raises(ValueError, match="run.default_shot"):
            apply_config_overrides(cfg, ["run.default_shot=abc"])
