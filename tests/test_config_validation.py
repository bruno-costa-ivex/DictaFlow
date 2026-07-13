"""
Tests for Config's YAML loading and validation logic.

Config.py has no dependency on the OS-bound packages conftest.py stubs
(pynput/pyperclip/mlx-whisper) — it only touches PyYAML, which is a normal
dependency — so these tests write real, temporary config.yaml files via
pytest's tmp_path fixture rather than mocking anything.
"""

import pytest
import yaml

from config import Config

MINIMAL_VALID_CONFIG = """
audio:
  sample_rate: 16000
  channels: 1
model:
  size: base
  device: cpu
  compute_type: int8
keyboard:
  modifier_key: right_cmd
  trigger_key: ""
"""


def _write_config(tmp_path, content: str) -> str:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(content)
    return str(config_file)


def test_minimal_valid_config_loads_ok(tmp_path):
    path = _write_config(tmp_path, MINIMAL_VALID_CONFIG)
    config = Config(path)
    assert config.audio == {"sample_rate": 16000, "channels": 1}
    assert config.model["size"] == "base"
    assert config.keyboard["modifier_key"] == "right_cmd"


def test_nonexistent_file_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        Config("/nonexistent/path/config.yaml")


def test_empty_yaml_file_raises_clear_value_error(tmp_path):
    path = _write_config(tmp_path, "")
    with pytest.raises(ValueError, match="empty or invalid"):
        Config(path)


def test_yaml_that_is_not_a_mapping_raises_clear_value_error(tmp_path):
    path = _write_config(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(ValueError, match="empty or invalid"):
        Config(path)


@pytest.mark.parametrize("missing_section", ["audio", "model", "keyboard"])
def test_missing_top_level_section_raises(tmp_path, missing_section):
    # Drop the section under test by rebuilding the YAML without its block.
    sections = {
        "audio": "audio:\n  sample_rate: 16000\n  channels: 1\n",
        "model": "model:\n  size: base\n  device: cpu\n  compute_type: int8\n",
        "keyboard": 'keyboard:\n  modifier_key: right_cmd\n  trigger_key: ""\n',
    }
    del sections[missing_section]
    path = _write_config(tmp_path, "\n".join(sections.values()))

    with pytest.raises(ValueError, match=f"Missing '{missing_section}' section"):
        Config(path)


@pytest.mark.parametrize(
    "section,missing_key",
    [
        ("audio", "sample_rate"),
        ("audio", "channels"),
        ("model", "size"),
        ("model", "device"),
        ("model", "compute_type"),
        ("keyboard", "modifier_key"),
        ("keyboard", "trigger_key"),
    ],
)
def test_missing_required_leaf_key_raises(tmp_path, section, missing_key):
    sections = {
        "audio": {"sample_rate": 16000, "channels": 1},
        "model": {"size": "base", "device": "cpu", "compute_type": "int8"},
        "keyboard": {"modifier_key": "right_cmd", "trigger_key": ""},
    }
    del sections[section][missing_key]

    path = _write_config(tmp_path, yaml.dump(sections))

    with pytest.raises(ValueError, match=missing_key):
        Config(path)


def test_section_that_is_not_a_mapping_raises(tmp_path):
    path = _write_config(
        tmp_path,
        'audio: "not a mapping"\n'
        "model:\n  size: base\n  device: cpu\n  compute_type: int8\n"
        'keyboard:\n  modifier_key: right_cmd\n  trigger_key: ""\n',
    )
    with pytest.raises(ValueError, match="must be a mapping"):
        Config(path)


def test_invalid_model_size_raises(tmp_path):
    path = _write_config(
        tmp_path,
        MINIMAL_VALID_CONFIG.replace("size: base", "size: gigantic"),
    )
    with pytest.raises(ValueError, match="Invalid model size"):
        Config(path)


def test_invalid_model_device_raises(tmp_path):
    path = _write_config(
        tmp_path,
        MINIMAL_VALID_CONFIG.replace("device: cpu", "device: quantum"),
    )
    with pytest.raises(ValueError, match="Invalid device"):
        Config(path)


def test_invalid_compute_type_raises_for_non_mlx_device(tmp_path):
    path = _write_config(
        tmp_path,
        MINIMAL_VALID_CONFIG.replace("compute_type: int8", "compute_type: nonsense"),
    )
    with pytest.raises(ValueError, match="Invalid compute type"):
        Config(path)


def test_mlx_device_bypasses_compute_type_value_validation(tmp_path):
    """compute_type's key must still be present (checked above), but its
    value is never validated against the enum for the mlx device."""
    path = _write_config(
        tmp_path,
        MINIMAL_VALID_CONFIG.replace("device: cpu", "device: mlx").replace(
            "compute_type: int8", "compute_type: garbage"
        ),
    )
    config = Config(path)
    assert config.model["compute_type"] == "garbage"


def test_accessor_properties_default_to_empty_dict_when_absent(tmp_path):
    path = _write_config(tmp_path, MINIMAL_VALID_CONFIG)
    config = Config(path)
    assert config.app == {}
    assert config.notifications == {}


def test_get_dotted_path_traversal(tmp_path):
    path = _write_config(tmp_path, MINIMAL_VALID_CONFIG)
    config = Config(path)
    assert config.get("audio.sample_rate") == 16000
    assert config.get("model.size") == "base"


def test_get_returns_default_when_key_missing(tmp_path):
    path = _write_config(tmp_path, MINIMAL_VALID_CONFIG)
    config = Config(path)
    assert config.get("audio.nonexistent", "fallback") == "fallback"
    assert config.get("nonexistent_section.key", "fallback") == "fallback"


def test_get_returns_default_when_intermediate_node_not_a_dict(tmp_path):
    path = _write_config(tmp_path, MINIMAL_VALID_CONFIG)
    config = Config(path)
    # "audio.sample_rate" is an int, not a dict — traversing past it must
    # fall back to the default rather than raising.
    assert config.get("audio.sample_rate.nested", "fallback") == "fallback"
