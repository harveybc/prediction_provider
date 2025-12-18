#!/usr/bin/env python3
"""
Default Pipeline Plugin

This plugin orchestrates the prediction system components, managing the flow of data
from the feeder to the predictor and handling the results.
"""

import time
import json
from datetime import datetime, timezone
from app.models import create_database_engine, get_session, Prediction

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
        self.engine = None
        
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
            "database_connected": self.engine is not None,
            "last_prediction_status": self.get_last_prediction_status()
        })
        return debug_info

    def get_last_prediction_status(self):
        """
        Retrieves the status of the most recent prediction.
        """
        if not self.engine:
            return "db not connected"
        session = get_session(self.engine)
        try:
            prediction = session.query(Prediction).order_by(Prediction.id.desc()).first()
            return prediction.status if prediction else "no predictions yet"
        except Exception as e:
            return f"db error: {e}"
        finally:
            session.close()

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

    def run_request(self, request: dict) -> dict:
        """Run a single prediction request and return a structured result.

        Expected request keys (best-effort):
        - baseline_datetime: ISO string for the baseline timestamp
        - horizons: list[int] of steps ahead (e.g. [1,2,3])
        - date_column / target_column: column names in feeder data
        """
        if not self.predictor_plugin or not self.feeder_plugin:
            raise RuntimeError("Pipeline not initialized with predictor+feeder")

        input_df = self.feeder_plugin.fetch()
        if input_df is None or input_df.empty:
            raise RuntimeError("Feeder returned no data")

        if hasattr(self.predictor_plugin, "predict_request"):
            return self.predictor_plugin.predict_request(input_df, request)

        raise RuntimeError("Predictor plugin does not implement predict_request")

    def _initialize_database(self):
        """
        Initialize the SQLite database for storing predictions.
        """
        db_path = self.params.get("db_path")
        if not db_path:
            print("Warning: DB path is not configured.")
            return

        try:
            self.engine = create_database_engine(f"sqlite:///{db_path}")
            print(f"Database initialized at {db_path}")
        except Exception as e:
            print(f"Database initialization failed: {e}")
            self.engine = None

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
        if not self.engine:
            print("Database not connected.")
            return False
        return True

    def request_prediction(self):
        """
        Requests a new prediction, creating a pending entry in the database.
        Returns the ID of the new prediction request.
        """
        if not self.engine:
            return None
        session = get_session(self.engine)
        try:
            new_prediction = Prediction()
            session.add(new_prediction)
            session.commit()
            return new_prediction.id
        except Exception as e:
            print(f"Failed to request prediction: {e}")
            session.rollback()
            return None
        finally:
            session.close()

    def _run_single_cycle(self, prediction_id):
        """
        Execute a single prediction cycle for a given prediction ID.
        """
        if not self._validate_system():
            print("Cannot run prediction cycle: system not properly initialized.")
            return

        try:
            print(f"\n--- New prediction cycle started at {datetime.now(timezone.utc).isoformat()} ---")

            # 1. Fetch data
            print("Fetching data...")
            input_df = self.feeder_plugin.fetch()

            if input_df is None or input_df.empty:
                print("Warning: Failed to fetch data or data is empty. Skipping prediction cycle.")
                return

            print(f"Data fetched successfully. Shape: {input_df.shape}")

            # 2. Make prediction
            print("Making prediction...")
            prediction_output = self.predictor_plugin.predict_with_uncertainty(input_df)

            if not prediction_output:
                print("Warning: Prediction failed. Skipping storage.")
                self._update_prediction_status(prediction_id, 'failed')
                return

            print("Prediction successful.")

            # 3. Store prediction
            self._store_prediction(prediction_id, prediction_output)

        except Exception as e:
            print(f"An error occurred in the prediction pipeline: {e}")
            self._update_prediction_status(prediction_id, 'failed')

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
            prediction_id = self.request_prediction()
            if prediction_id:
                self._run_single_cycle(prediction_id)
            
            # Wait for the next interval
            interval = self.params.get("prediction_interval", 300)
            print(f"--- Cycle finished. Waiting for {interval} seconds... ---")
            time.sleep(interval)

    def _update_prediction_status(self, prediction_id, status):
        """
        Updates the status of a prediction in the database.
        """
        if not self.engine:
            return
        session = get_session(self.engine)
        try:
            prediction = session.query(Prediction).filter_by(id=prediction_id).first()
            if prediction:
                prediction.status = status
                session.commit()
        except Exception as e:
            print(f"Failed to update prediction status: {e}")
            session.rollback()
        finally:
            session.close()

    def _store_prediction(self, prediction_id, prediction_output):
        """
        Store the prediction output in the database for a given prediction ID.
        """
        if not self.engine:
            print("Cannot store prediction: database not connected.")
            self._update_prediction_status(prediction_id, 'failed')
            return

        session = get_session(self.engine)
        try:
            prediction = session.query(Prediction).filter_by(id=prediction_id).first()
            if prediction:
                prediction.prediction_data = prediction_output
                prediction.status = 'completed'
                session.commit()
                print(f"Successfully stored prediction for ID: {prediction_id}")
            else:
                print(f"Prediction with ID {prediction_id} not found.")
                self._update_prediction_status(prediction_id, 'failed')

        except Exception as e:
            print(f"Failed to store prediction: {e}")
            session.rollback()
            self._update_prediction_status(prediction_id, 'failed')
        finally:
            session.close()

    def get_system_status(self):
        """
        Get the overall system status.
        """
        return {
            "system_ready": self._validate_system(),
            "pipeline_running": self.running,
            "last_prediction_status": self.get_last_prediction_status()
        }
    
    def stop(self):
        """
        Stop the pipeline execution.
        """
        self.running = False
    
    def cleanup(self):
        """
        Cleanup pipeline resources.
        """
        self.stop()
        print("Pipeline cleanup completed")
