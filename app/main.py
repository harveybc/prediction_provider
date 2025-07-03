#!/usr/bin/env python3
"""
main.py

Entry point for the Prediction Provider application. This script orchestrates:
- Loading and merging configurations (CLI, files).
- Initializing all plugins: Core, Endpoints, Feeder, Pipeline, and Predictor.
- Starting the core plugin to launch the FastAPI application.
"""

import sys
from typing import Any, Dict
import logging

# Add the project root to the Python path to allow for absolute imports
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config_handler import load_config, remote_load_config
from app.cli import parse_args
from app.config import DEFAULT_VALUES
from app.plugin_loader import load_plugin
from app.config_merger import merge_config, process_unknown_args

# Import the FastAPI app for tests
from plugins_core.default_core import app

def setup_logging(level=logging.INFO):
    """Setup logging configuration."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log')
        ]
    )
    return logging.getLogger(__name__)

def main():
    """
    Orchestrates the execution of the Prediction Provider system.
    """
    print("--- Initializing Prediction Provider ---")

    # 1. Configuration Loading
    args, unknown_args = parse_args()
    cli_args: Dict[str, Any] = vars(args)
    config: Dict[str, Any] = DEFAULT_VALUES.copy()
    file_config: Dict[str, Any] = {}

    if args.load_config:
        try:
            file_config = load_config(args.load_config)
            print(f"Loaded local config from: {args.load_config}")
        except Exception as e:
            print(f"Failed to load local configuration: {e}")
            sys.exit(1)

    # First merge pass (without plugin-specific parameters)
    print("Merging configuration (first pass)...")
    unknown_args_dict = process_unknown_args(unknown_args)
    config = merge_config(config, {}, {}, file_config, cli_args, unknown_args_dict)

    # 2. Plugin Loading
    plugin_types = ['core', 'endpoints', 'feeder', 'pipeline', 'predictor']
    plugins = {}

    for plugin_type in plugin_types:
        plugin_name = config.get(f'{plugin_type}_plugin', f'default_{plugin_type}')
        print(f"Loading {plugin_type.capitalize()} Plugin: {plugin_name}")
        try:
            plugin_class, _ = load_plugin(f'{plugin_type}.plugins', plugin_name)
            plugin_instance = plugin_class(config)
            plugin_instance.set_params(**config)
            plugins[plugin_type] = plugin_instance
        except Exception as e:
            print(f"Failed to load or initialize {plugin_type.capitalize()} Plugin '{plugin_name}': {e}")
            sys.exit(1)

    # Second merge pass (with all plugin parameters)
    print("Merging configuration (second pass, with plugin params)...")
    for plugin_type, plugin_instance in plugins.items():
        config = merge_config(config, plugin_instance.plugin_params, {}, file_config, cli_args, unknown_args_dict)

    # 3. Start Application using the Core Plugin
    core_plugin = plugins.get('core')
    if not core_plugin:
        print("Fatal: Core plugin not found. Cannot start application.")
        sys.exit(1)
        
    # Pass all loaded plugins to the core system
    core_plugin.set_plugins(plugins)

    try:
        print("Starting Core Plugin...")
        core_plugin.start()
    except Exception as e:
        print(f"An unexpected error occurred while starting the core plugin: {e}")
        core_plugin.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
