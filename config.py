#!/usr/bin/env python3
"""
Configuration Management
Loads and validates configuration from config.yaml
"""

import yaml
import os
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
        
        return config
    
    def _validate_config(self):
        """Validate configuration values."""
        # Validate audio settings
        if 'audio' not in self.config:
            raise ValueError("Missing 'audio' section in config.yaml")
        
        # Validate model settings
        if 'model' not in self.config:
            raise ValueError("Missing 'model' section in config.yaml")
        
        # Validate keyboard settings
        if 'keyboard' not in self.config:
            raise ValueError("Missing 'keyboard' section in config.yaml")
        
        # Validate model size
        valid_sizes = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
        if self.config['model']['size'] not in valid_sizes:
            raise ValueError(
                f"Invalid model size: {self.config['model']['size']}\n"
                f"Valid options: {', '.join(valid_sizes)}"
            )
        
        # Validate device
        valid_devices = ["cpu", "cuda", "mlx"]
        if self.config['model']['device'] not in valid_devices:
            raise ValueError(
                f"Invalid device: {self.config['model']['device']}\n"
                f"Valid options: {', '.join(valid_devices)}"
            )

        # compute_type is not used by mlx — skip validation for that device
        if self.config['model']['device'] != "mlx":
            valid_compute_types = ["int8", "float16", "float32"]
            if self.config['model']['compute_type'] not in valid_compute_types:
                raise ValueError(
                    f"Invalid compute type: {self.config['model']['compute_type']}\n"
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

