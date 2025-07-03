#!/usr/bin/env python3
"""
Default Pipeline Plugin

This plugin orchestrates the prediction system components, managing the flow of data
from the feeder to the predictor and handling the results.
"""

import time
import json
from datetime import datetime
import sqlite3

class DefaultPipelinePlugin:
    """
    Default pipeline plugin for coordinating prediction system components.
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "pipeline_enabled": True,
        "prediction_interval": 300,  # seconds
        "db_path": "prediction_provider.db",
        "enable_logging": True,
        "log_level": "INFO"
    }
    
    # Debug variables for monitoring
    plugin_debug_vars = [
        "pipeline_enabled", "prediction_interval", "db_path", "enable_logging"
    ]
    
    def __init__(self, config=None):
        """
        Initialize the pipeline plugin.
        
        Args:
            config (dict): Configuration parameters
        """
        self.params = self.plugin_params.copy()
        self.predictor_plugin = None
        self.feeder_plugin = None
        self.running = False
        self.db_conn = None
        
        if config:
            self.set_params(**config)
    
    def set_params(self, **kwargs):
        """
        Update plugin parameters with provided configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        for key, value in kwargs.items():
            self.params[key] = value

        if 'db_path' in kwargs:
            self._initialize_database()

    def get_debug_info(self):
        """
        Get debug information for this plugin.
        
        Returns:
            dict: Debug information
        """
        debug_info = {var: self.params.get(var) for var in self.plugin_debug_vars}
        debug_info.update({
            "running": self.running,
            "predictor_loaded": self.predictor_plugin is not None,
            "feeder_loaded": self.feeder_plugin is not None,
            "database_connected": self.db_conn is not None
        })
        return debug_info

    def initialize(self, predictor_plugin, feeder_plugin):
        """
        Initialize the pipeline with the provided plugins.
        
        Args:
            predictor_plugin: An instance of the predictor plugin.
            feeder_plugin: An instance of the feeder plugin.
        """
        print("Initializing pipeline...")
        self.predictor_plugin = predictor_plugin
        self.feeder_plugin = feeder_plugin
        self._initialize_database()
        
        if self._validate_system():
            print("Pipeline initialized successfully.")
        else:
            print("Warning: Pipeline initialization incomplete.")

    def _initialize_database(self):
        """
        Initialize the SQLite database for storing predictions.
        """
        db_path = self.params.get("db_path")
        if not db_path:
            print("Warning: DB path is not configured.")
            return

        try:
            self.db_conn = sqlite3.connect(db_path, check_same_thread=False)
            cursor = self.db_conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_timestamp TEXT NOT NULL,
                prediction TEXT NOT NULL,
                uncertainty TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
            ''')
            self.db_conn.commit()
            print(f"Database initialized at {db_path}")
        except sqlite3.Error as e:
            print(f"Database initialization failed: {e}")
            self.db_conn = None

    def _validate_system(self):
        """
        Validate that all required components are available and configured.
        """
        if not self.params.get("pipeline_enabled", True):
            print("Pipeline is disabled.")
            return False
        if not self.predictor_plugin:
            print("Predictor plugin not available.")
            return False
        if not self.feeder_plugin:
            print("Feeder plugin not available.")
            return False
        if not self.db_conn:
            print("Database not connected.")
            return False
        return True

    def run(self):
        """
        The main loop of the prediction pipeline.
        """
        if not self._validate_system():
            print("Cannot run pipeline: system not properly initialized.")
            return

        self.running = True
        print("Prediction pipeline started.")

        while self.running:
            try:
                print(f"\n--- New prediction cycle started at {datetime.utcnow().isoformat()} ---")
                
                # 1. Fetch data
                print("Fetching data...")
                data_result = self.feeder_plugin.fetch_data_for_prediction()
                
                if not data_result or 'data' not in data_result or data_result['data'].empty:
                    print("Warning: Failed to fetch data or data is empty. Skipping prediction cycle.")
                    time.sleep(self.params.get("prediction_interval", 300))
                    continue

                input_df = data_result['data']
                print(f"Data fetched successfully. Shape: {input_df.shape}")

                # 2. Make prediction
                print("Making prediction...")
                prediction_output = self.predictor_plugin.predict_with_uncertainty(input_df)
                
                if not prediction_output:
                    print("Warning: Prediction failed. Skipping storage.")
                    continue

                print("Prediction successful.")

                # 3. Store prediction
                self._store_prediction(prediction_output)

            except Exception as e:
                print(f"An error occurred in the prediction pipeline: {e}")
            
            # Wait for the next interval
            interval = self.params.get("prediction_interval", 300)
            print(f"--- Cycle finished. Waiting for {interval} seconds... ---")
            time.sleep(interval)

    def _store_prediction(self, prediction_output):
        """
        Store the prediction output in the database.
        """
        if not self.db_conn:
            print("Warning: Cannot store prediction, database not connected.")
            return

        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                "INSERT INTO predictions (prediction_timestamp, prediction, uncertainty, metadata) VALUES (?, ?, ?, ?)",
                (
                    prediction_output['prediction_timestamp'],
                    json.dumps(prediction_output['prediction']),
                    json.dumps(prediction_output['uncertainty']),
                    json.dumps(prediction_output['metadata'])
                )
            )
            self.db_conn.commit()
            print(f"Prediction stored successfully at {prediction_output['prediction_timestamp']}")
        except sqlite3.Error as e:
            print(f"Failed to store prediction: {e}")

    def stop(self):
        """
        Stop the prediction pipeline.
        """
        self.running = False
        print("Prediction pipeline stopping...")
        if self.db_conn:
            self.db_conn.close()
            print("Database connection closed.")

    def get_system_status(self):
        """
        Get the current status of the prediction system.
        """
        return {
            'pipeline_enabled': self.params.get("pipeline_enabled", True),
            'pipeline_running': self.running,
            'predictor_available': self.predictor_plugin is not None,
            'feeder_available': self.feeder_plugin is not None,
            'system_ready': self._validate_system()
        }

    def cleanup(self):
        """
        Cleanup pipeline resources.
        """
        self.stop()
        print("Pipeline cleanup completed")
