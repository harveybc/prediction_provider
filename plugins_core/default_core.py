#!/usr/bin/env python3
"""
Default Core Plugin for Prediction Provider.

This plugin is the central orchestrator of the application. It handles:
- Loading and managing all other plugins (feeder, predictor, pipeline, endpoints).
- Initializing the system in the correct order.
- Starting and stopping the application services.
"""

import os
import importlib
import threading

class DefaultCorePlugin:
    """
    The central core plugin for the Prediction Provider application.
    """

    plugin_params = {
        "plugin_directories": [
            "plugins_feeder",
            "plugins_predictor",
            "plugins_pipeline",
            "plugins_endpoints"
        ]
    }

    plugin_debug_vars = ["plugin_directories"]

    def __init__(self, config):
        """
        Initializes the core plugin.

        Args:
            config (dict): The global application configuration.
        """
        self.params = self.plugin_params.copy()
        self.params.update(config)
        self.plugins = {}
        self.pipeline_thread = None

    def set_params(self, **kwargs):
        """
        Updates the core parameters.
        """
        self.params.update(kwargs)

    def get_debug_info(self):
        """
        Returns debug information for the core plugin.
        """
        info = {var: self.params.get(var) for var in self.plugin_debug_vars}
        info["loaded_plugins"] = list(self.plugins.keys())
        return info

    def load_plugins(self):
        """
        Dynamically loads all plugins from the specified directories.
        """
        print("--- Loading Plugins ---")
        plugin_dirs = self.params.get("plugin_directories", [])
        for plugin_dir in plugin_dirs:
            if not os.path.isdir(plugin_dir):
                print(f"Warning: Plugin directory not found: {plugin_dir}")
                continue

            for filename in os.listdir(plugin_dir):
                if filename.endswith(".py") and not filename.startswith("__init__"):
                    module_name = f"{plugin_dir}.{filename[:-3]}"
                    try:
                        module = importlib.import_module(module_name)
                        for item_name in dir(module):
                            item = getattr(module, item_name)
                            if isinstance(item, type) and hasattr(item, 'plugin_params'):
                                plugin_name = module_name.replace('.', '_')
                                self.plugins[plugin_name] = item(self.params)
                                print(f"Successfully loaded plugin: {plugin_name}")
                    except Exception as e:
                        print(f"Failed to load plugin from {module_name}: {e}")
        print("--- Plugin Loading Finished ---")

    def start(self):
        """
        Starts the application by initializing plugins and running the main pipeline.
        """
        print("--- Starting Application ---")
        self.load_plugins()

        # Retrieve specific plugins
        feeder = self._get_plugin_by_type("plugins_feeder")
        predictor = self._get_plugin_by_type("plugins_predictor")
        pipeline = self._get_plugin_by_type("plugins_pipeline")
        endpoints = self._get_plugin_by_type("plugins_endpoints")

        if not all([feeder, predictor, pipeline]):
            print("Error: Core plugins (feeder, predictor, pipeline) are missing. Cannot start.")
            return

        # Initialize the pipeline
        print("Initializing the prediction pipeline...")
        pipeline.initialize(predictor_plugin=predictor, feeder_plugin=feeder)

        # Start the pipeline in a background thread
        self.pipeline_thread = threading.Thread(target=pipeline.run, daemon=True)
        self.pipeline_thread.start()
        print("Prediction pipeline is running in the background.")

        # Initialize and start the endpoints server if it exists
        if endpoints:
            print("Initializing and starting the endpoints server...")
            endpoints.initialize(pipeline_plugin=pipeline)
            endpoints.run()
        else:
            print("No endpoints plugin found. Running in headless mode.")
            # Keep the main thread alive to allow the pipeline to run
            self.pipeline_thread.join()

    def stop(self):
        """
        Stops the application and cleans up resources.
        """
        print("--- Stopping Application ---")
        pipeline = self._get_plugin_by_type("plugins_pipeline")
        if pipeline:
            pipeline.stop()
        
        if self.pipeline_thread and self.pipeline_thread.is_alive():
            self.pipeline_thread.join(timeout=10)

        print("Application stopped.")

    def _get_plugin_by_type(self, dir_prefix):
        """
        Finds the first loaded plugin from a given directory prefix.
        """
        for name, plugin in self.plugins.items():
            if name.startswith(dir_prefix):
                return plugin
        return None

# For backward compatibility
Plugin = DefaultCorePlugin
