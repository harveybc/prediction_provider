#!/usr/bin/env python3
"""
main.py

Entry point for the Prediction Provider application. This script orchestrates:
- Loading and merging configurations.
- Initializing the core plugin which manages the application lifecycle.
"""

import sys
import os
import signal

# Add the project root to the Python path to allow for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config_handler import load_config, remote_load_config
from app.cli import parse_args
from app.config import DEFAULT_VALUES
from plugins_core.default_core import DefaultCorePlugin

def main():
    """
    Orchestrates the execution of the Prediction Provider system.
    """
    print("--- Initializing Prediction Provider ---")

    # 1. Configuration Loading
    args, _ = parse_args()
    config = DEFAULT_VALUES.copy()
    cli_args = vars(args)

    if args.load_config:
        try:
            file_config = load_config(args.load_config)
            config.update(file_config)
            print(f"Loaded local config from: {args.load_config}")
        except Exception as e:
            print(f"Failed to load local configuration: {e}")
            sys.exit(1)

    # Merge CLI arguments, overriding file and default configs
    config.update({k: v for k, v in cli_args.items() if v is not None})

    # 2. Core Plugin Initialization
    core_plugin = DefaultCorePlugin(config)

    # 3. Graceful Shutdown Handler
    def shutdown_handler(signum, frame):
        print("\nShutdown signal received.")
        core_plugin.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # 4. Start Application
    try:
        core_plugin.start()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        core_plugin.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
