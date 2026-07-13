#!/usr/bin/env python3
"""
Configuration Management
Loads and validates configuration from config.yaml
"""

import yaml
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuration manager for the transcription tool."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration from YAML file.
        
        Args:
            config_path: Path to the configuration YAML file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_file = Path(self.config_path)

        if not config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                "Please create config.yaml in the same directory."
            )

        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError(
                f"Configuration file is empty or invalid: {self.config_path}\n"
                "Expected a YAML mapping with 'audio', 'model', and 'keyboard' sections."
            )

        return config

    def _require_section(self, section: str, keys) -> Dict[str, Any]:
        """Raise a clear ValueError if `section` is missing, isn't a mapping,
        or is missing any of `keys` — instead of letting a raw KeyError or
        TypeError surface later from wherever the value happens to first be
        accessed (e.g. main.py's audio_cfg['sample_rate'])."""
        if section not in self.config:
            raise ValueError(f"Missing '{section}' section in config.yaml")

        section_config = self.config[section]
        if not isinstance(section_config, dict):
            raise ValueError(
                f"'{section}' section in config.yaml must be a mapping, "
                f"got {type(section_config).__name__}"
            )

        missing = [k for k in keys if k not in section_config]
        if missing:
            raise ValueError(
                f"Missing required key(s) in '{section}' section: {', '.join(missing)}"
            )

        return section_config

    def _validate_config(self):
        """Validate configuration values."""
        self._require_section('audio', ['sample_rate', 'channels'])
        model_cfg = self._require_section('model', ['size', 'device', 'compute_type'])
        self._require_section('keyboard', ['modifier_key', 'trigger_key'])

        # Validate model size
        valid_sizes = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
        if model_cfg['size'] not in valid_sizes:
            raise ValueError(
                f"Invalid model size: {model_cfg['size']}\n"
                f"Valid options: {', '.join(valid_sizes)}"
            )

        # Validate device
        valid_devices = ["cpu", "cuda", "mlx"]
        if model_cfg['device'] not in valid_devices:
            raise ValueError(
                f"Invalid device: {model_cfg['device']}\n"
                f"Valid options: {', '.join(valid_devices)}"
            )

        # compute_type is not used by mlx — skip value validation for that
        # device (the key must still be present, checked above, since
        # Transcriber() is always constructed with a compute_type argument).
        if model_cfg['device'] != "mlx":
            valid_compute_types = ["int8", "float16", "float32"]
            if model_cfg['compute_type'] not in valid_compute_types:
                raise ValueError(
                    f"Invalid compute type: {model_cfg['compute_type']}\n"
                    f"Valid options: {', '.join(valid_compute_types)}"
                )
    
    @property
    def audio(self) -> Dict[str, Any]:
        """Get audio configuration."""
        return self.config.get('audio', {})
    
    @property
    def model(self) -> Dict[str, Any]:
        """Get model configuration."""
        return self.config.get('model', {})
    
    @property
    def keyboard(self) -> Dict[str, Any]:
        """Get keyboard configuration."""
        return self.config.get('keyboard', {})
    
    @property
    def app(self) -> Dict[str, Any]:
        """Get application configuration."""
        return self.config.get('app', {})

    @property
    def notifications(self) -> Dict[str, Any]:
        """Get notifications configuration."""
        return self.config.get('notifications', {})

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key path (e.g., 'audio.sample_rate')."""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value

