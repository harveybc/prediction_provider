#!/usr/bin/env python3
"""
Enhanced Pipeline Plugin with Real-Time Data Fetching

This plugin extends the default pipeline to support:
- Passing start/end dates to the feeder plugin
- Real-time data fetching with configurable parameters
- Better integration with the RealFeederPlugin
"""

import os as _os
_QUIET = _os.environ.get('PREDICTION_PROVIDER_QUIET', '0') == '1'

import time
import json
from datetime import datetime, timezone, timedelta
from app.models import create_database_engine, get_session, Prediction

class EnhancedPipelinePlugin:
    """
    Enhanced pipeline plugin with real-time data fetching capabilities.
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "pipeline_enabled": True,
        "prediction_interval": 300,  # seconds
        "db_path": "prediction_provider.db",
        "enable_logging": True,
        "log_level": "INFO",
        # New parameters for real-time data fetching
        "data_lookback_hours": 720,  # 30 days default lookback
        "additional_previous_ticks": 50,  # Extra ticks for technical indicators
        "use_custom_date_range": False,  # Whether to use custom start/end dates
        "custom_start_date": None,  # Custom start date (YYYY-MM-DD HH:MM:SS)
        "custom_end_date": None,   # Custom end date (YYYY-MM-DD HH:MM:SS)
        "real_time_mode": True     # Whether to fetch real-time data or use historical range
    }
    
    # Debug variables for monitoring
    plugin_debug_vars = [
        "pipeline_enabled", "prediction_interval", "db_path", "enable_logging",
        "data_lookback_hours", "additional_previous_ticks", "use_custom_date_range", "real_time_mode"
    ]
    
    def __init__(self, config=None):
        """
        Initialize the enhanced pipeline plugin.
        
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
            "last_prediction_status": self.get_last_prediction_status(),
            "feeder_supports_date_range": hasattr(self.feeder_plugin, 'fetch_data_for_period') if self.feeder_plugin else False
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
        if not _QUIET: print("Initializing enhanced pipeline...")
        self.predictor_plugin = predictor_plugin
        self.feeder_plugin = feeder_plugin
        self._initialize_database()
        
        # Check if feeder supports custom date ranges
        if hasattr(self.feeder_plugin, 'fetch_data_for_period'):
            if not _QUIET: print("✓ Feeder plugin supports custom date ranges")
        else:
            if not _QUIET: print("⚠ Feeder plugin does not support custom date ranges")
        
        if self._validate_system():
            if not _QUIET: print("Enhanced pipeline initialized successfully.")
        else:
            if not _QUIET: print("Warning: Pipeline initialization incomplete.")

    def _initialize_database(self):
        """
        Initialize the SQLite database for storing predictions.
        """
        db_path = self.params.get("db_path")
        if not db_path:
            if not _QUIET: print("Warning: DB path is not configured.")
            return

        try:
            self.engine = create_database_engine(f"sqlite:///{db_path}")
            if not _QUIET: print(f"Database initialized at {db_path}")
        except Exception as e:
            if not _QUIET: print(f"Database initialization failed: {e}")
            self.engine = None

    def _validate_system(self):
        """
        Validate that all required components are available and configured.
        """
        if not self.params.get("pipeline_enabled", True):
            if not _QUIET: print("Pipeline is disabled.")
            return False
        if not self.predictor_plugin:
            if not _QUIET: print("Predictor plugin not available.")
            return False
        if not self.feeder_plugin:
            if not _QUIET: print("Feeder plugin not available.")
            return False
        if not self.engine:
            if not _QUIET: print("Database not connected.")
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
            if not _QUIET: print(f"Failed to request prediction: {e}")
            session.rollback()
            return None
        finally:
            session.close()

    def _calculate_date_range(self):
        """
        Calculate the start and end dates for data fetching based on configuration.
        
        Returns:
            tuple: (start_date_str, end_date_str, additional_previous_ticks)
        """
        if self.params.get("use_custom_date_range", False):
            # Use custom date range if specified
            start_date = self.params.get("custom_start_date")
            end_date = self.params.get("custom_end_date")
            
            if start_date and end_date:
                if not _QUIET: print(f"Using custom date range: {start_date} to {end_date}")
                return start_date, end_date, self.params.get("additional_previous_ticks", 50)
        
        # Calculate real-time or recent data range
        if self.params.get("real_time_mode", True):
            # Real-time mode: fetch recent data up to now
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=self.params.get("data_lookback_hours", 720))
        else:
            # Use current time as reference but allow for some delay
            end_date = datetime.now() - timedelta(minutes=5)  # 5-minute delay for data availability
            start_date = end_date - timedelta(hours=self.params.get("data_lookback_hours", 720))
        
        start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
        end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')
        
        if not _QUIET: print(f"Calculated date range: {start_date_str} to {end_date_str}")
        return start_date_str, end_date_str, self.params.get("additional_previous_ticks", 50)

    def _fetch_data_with_date_range(self):
        """
        Fetch data using the enhanced feeder with date range support.
        
        Returns:
            DataFrame: Fetched data or None if failed
        """
        try:
            # Check if feeder supports date range fetching
            if hasattr(self.feeder_plugin, 'fetch_data_for_period'):
                # Calculate date range
                start_date, end_date, additional_ticks = self._calculate_date_range()
                
                if not _QUIET: print(f"Fetching data with parameters:")
                if not _QUIET: print(f"  Start: {start_date}")
                if not _QUIET: print(f"  End: {end_date}")
                if not _QUIET: print(f"  Additional ticks: {additional_ticks}")
                
                # Fetch data for the specified period
                input_df = self.feeder_plugin.fetch_data_for_period(
                    start_date=start_date,
                    end_date=end_date,
                    additional_previous_ticks=additional_ticks
                )
                
                return input_df
            else:
                # Fallback to standard fetch method
                if not _QUIET: print("Feeder doesn't support date ranges, using standard fetch...")
                return self.feeder_plugin.fetch()
                
        except Exception as e:
            if not _QUIET: print(f"Error in enhanced data fetching: {e}")
            # Fallback to standard fetch
            try:
                return self.feeder_plugin.fetch()
            except Exception as fallback_e:
                if not _QUIET: print(f"Fallback fetch also failed: {fallback_e}")
                return None

    def _run_single_cycle(self, prediction_id):
        """
        Execute a single prediction cycle for a given prediction ID.
        """
        if not self._validate_system():
            if not _QUIET: print("Cannot run prediction cycle: system not properly initialized.")
            return

        try:
            if not _QUIET: print(f"\n--- New enhanced prediction cycle started at {datetime.now(timezone.utc).isoformat()} ---")

            # 1. Fetch data with enhanced date range support
            if not _QUIET: print("Fetching data with enhanced date range support...")
            input_df = self._fetch_data_with_date_range()

            if input_df is None or input_df.empty:
                if not _QUIET: print("Warning: Failed to fetch data or data is empty. Skipping prediction cycle.")
                self._update_prediction_status(prediction_id, 'failed')
                return

            if not _QUIET: print(f"Data fetched successfully. Shape: {input_df.shape}")
            if not _QUIET: print(f"Date range: {input_df['DATE_TIME'].min()} to {input_df['DATE_TIME'].max()}")

            # 2. Make prediction
            if not _QUIET: print("Making prediction...")
            prediction_output = self.predictor_plugin.predict_with_uncertainty(input_df)

            if not prediction_output:
                if not _QUIET: print("Warning: Prediction failed. Skipping storage.")
                self._update_prediction_status(prediction_id, 'failed')
                return

            if not _QUIET: print("Prediction successful.")

            # 3. Store prediction
            self._store_prediction(prediction_id, prediction_output)

        except Exception as e:
            if not _QUIET: print(f"An error occurred in the enhanced prediction pipeline: {e}")
            import traceback
            traceback.print_exc()
            self._update_prediction_status(prediction_id, 'failed')

    def run(self):
        """
        The main loop of the enhanced prediction pipeline.
        """
        if not self._validate_system():
            if not _QUIET: print("Cannot run pipeline: system not properly initialized.")
            return

        self.running = True
        if not _QUIET: print("Enhanced prediction pipeline started.")
        if not _QUIET: print(f"Configuration:")
        if not _QUIET: print(f"  Real-time mode: {self.params.get('real_time_mode', True)}")
        if not _QUIET: print(f"  Data lookback: {self.params.get('data_lookback_hours', 720)} hours")
        if not _QUIET: print(f"  Prediction interval: {self.params.get('prediction_interval', 300)} seconds")
        if not _QUIET: print(f"  Additional ticks: {self.params.get('additional_previous_ticks', 50)}")

        while self.running:
            prediction_id = self.request_prediction()
            if prediction_id:
                self._run_single_cycle(prediction_id)
            
            # Wait for the next interval
            interval = self.params.get("prediction_interval", 300)
            if not _QUIET: print(f"--- Cycle finished. Waiting for {interval} seconds... ---")
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
            if not _QUIET: print(f"Failed to update prediction status: {e}")
            session.rollback()
        finally:
            session.close()

    def _store_prediction(self, prediction_id, prediction_output):
        """
        Store the prediction output in the database for a given prediction ID.
        """
        if not self.engine:
            if not _QUIET: print("Cannot store prediction: database not connected.")
            self._update_prediction_status(prediction_id, 'failed')
            return

        session = get_session(self.engine)
        try:
            prediction = session.query(Prediction).filter_by(id=prediction_id).first()
            if prediction:
                prediction.prediction_data = prediction_output
                prediction.status = 'completed'
                session.commit()
                if not _QUIET: print(f"Successfully stored prediction for ID: {prediction_id}")
            else:
                if not _QUIET: print(f"Prediction with ID {prediction_id} not found.")
                self._update_prediction_status(prediction_id, 'failed')

        except Exception as e:
            if not _QUIET: print(f"Failed to store prediction: {e}")
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
            "last_prediction_status": self.get_last_prediction_status(),
            "enhanced_features": {
                "date_range_support": hasattr(self.feeder_plugin, 'fetch_data_for_period') if self.feeder_plugin else False,
                "real_time_mode": self.params.get('real_time_mode', True),
                "custom_date_range": self.params.get('use_custom_date_range', False)
            }
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
        if not _QUIET: print("Enhanced pipeline cleanup completed")

    # New methods for enhanced functionality
    
    def set_custom_date_range(self, start_date: str, end_date: str):
        """
        Set a custom date range for data fetching.
        
        Args:
            start_date (str): Start date in 'YYYY-MM-DD HH:MM:SS' format
            end_date (str): End date in 'YYYY-MM-DD HH:MM:SS' format
        """
        self.params['use_custom_date_range'] = True
        self.params['custom_start_date'] = start_date
        self.params['custom_end_date'] = end_date
        if not _QUIET: print(f"Custom date range set: {start_date} to {end_date}")
    
    def enable_real_time_mode(self, lookback_hours: int = 720):
        """
        Enable real-time mode with specified lookback period.
        
        Args:
            lookback_hours (int): Hours to look back from current time
        """
        self.params['real_time_mode'] = True
        self.params['use_custom_date_range'] = False
        self.params['data_lookback_hours'] = lookback_hours
        if not _QUIET: print(f"Real-time mode enabled with {lookback_hours} hours lookback")
    
    def run_single_prediction(self, start_date: str = None, end_date: str = None):
        """
        Run a single prediction cycle with optional custom date range.
        
        Args:
            start_date (str, optional): Custom start date
            end_date (str, optional): Custom end date
            
        Returns:
            dict: Prediction results or error information
        """
        if start_date and end_date:
            original_custom = self.params.get('use_custom_date_range', False)
            original_start = self.params.get('custom_start_date')
            original_end = self.params.get('custom_end_date')
            
            # Temporarily set custom date range
            self.set_custom_date_range(start_date, end_date)
            
        try:
            prediction_id = self.request_prediction()
            if prediction_id:
                self._run_single_cycle(prediction_id)
                return {"status": "success", "prediction_id": prediction_id}
            else:
                return {"status": "error", "message": "Failed to create prediction request"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
        finally:
            # Restore original settings if they were changed
            if start_date and end_date:
                self.params['use_custom_date_range'] = original_custom
                self.params['custom_start_date'] = original_start
                self.params['custom_end_date'] = original_end
