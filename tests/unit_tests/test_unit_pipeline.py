import unittest
from unittest.mock import MagicMock, patch
import time

# Assuming the pipeline plugin is in this path
from plugins_pipeline.default_pipeline import DefaultPipelinePlugin

class TestUnitPipeline(unittest.TestCase):
    """
    Unit tests for the DefaultPipelinePlugin.
    
    These tests verify the pipeline's coordination logic, database interaction,
    and plugin orchestration without actually running predictions.
    """

    def setUp(self):
        """Set up a fresh instance of the pipeline for each test."""
        self.pipeline = DefaultPipelinePlugin()

    def test_pipeline_initialization(self):
        """
        Test Case 5.1: Verify the pipeline initializes with correct default parameters.
        """
        # Assert default parameters are set correctly
        self.assertTrue(self.pipeline.params["pipeline_enabled"])
        self.assertEqual(self.pipeline.params["prediction_interval"], 300)
        self.assertEqual(self.pipeline.params["db_path"], "prediction_provider.db")
        self.assertTrue(self.pipeline.params["enable_logging"])
        self.assertEqual(self.pipeline.params["log_level"], "INFO")
        
        # Assert initial state
        self.assertFalse(self.pipeline.running)
        self.assertIsNone(self.pipeline.predictor_plugin)
        self.assertIsNone(self.pipeline.feeder_plugin)

    def test_pipeline_set_params(self):
        """
        Test Case 5.2: Verify parameter updates work correctly.
        """
        # Arrange
        new_params = {
            "prediction_interval": 600,
            "enable_logging": False,
            "log_level": "DEBUG"
        }
        
        # Act
        self.pipeline.set_params(**new_params)
        
        # Assert
        self.assertEqual(self.pipeline.params["prediction_interval"], 600)
        self.assertFalse(self.pipeline.params["enable_logging"])
        self.assertEqual(self.pipeline.params["log_level"], "DEBUG")
        # Verify unchanged parameters remain the same
        self.assertTrue(self.pipeline.params["pipeline_enabled"])

    def test_pipeline_initialize_plugins(self):
        """
        Test Case 5.3: Verify plugin initialization works correctly.
        """
        # Arrange
        mock_predictor = MagicMock()
        mock_feeder = MagicMock()
        
        # Mock the database initialization and validation
        with patch.object(self.pipeline, '_initialize_database'), \
             patch.object(self.pipeline, '_validate_system', return_value=True):
            
            # Act
            self.pipeline.initialize(mock_predictor, mock_feeder)
            
            # Assert
            self.assertEqual(self.pipeline.predictor_plugin, mock_predictor)
            self.assertEqual(self.pipeline.feeder_plugin, mock_feeder)

    @patch('plugins_pipeline.default_pipeline.create_database_engine')
    def test_pipeline_database_initialization(self, mock_create_engine):
        """
        Test Case 5.4: Verify database initialization works correctly.
        """
        # Arrange
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # Act
        self.pipeline._initialize_database()
        
        # Assert
        mock_create_engine.assert_called_once_with(f"sqlite:///{self.pipeline.params['db_path']}")
        self.assertEqual(self.pipeline.engine, mock_engine)

    def test_pipeline_validate_system_success(self):
        """
        Test Case 5.5: Verify system validation passes when all components are available.
        """
        # Arrange
        self.pipeline.predictor_plugin = MagicMock()
        self.pipeline.feeder_plugin = MagicMock()
        self.pipeline.engine = MagicMock()
        self.pipeline.params["pipeline_enabled"] = True
        
        # Act
        result = self.pipeline._validate_system()
        
        # Assert
        self.assertTrue(result)

    def test_pipeline_validate_system_failure(self):
        """
        Test Case 5.6: Verify system validation fails when components are missing.
        """
        # Arrange - leave plugins and engine as None
        self.pipeline.params["pipeline_enabled"] = True
        
        # Act
        result = self.pipeline._validate_system()
        
        # Assert
        self.assertFalse(result)

    @patch('plugins_pipeline.default_pipeline.get_session')
    def test_request_prediction(self, mock_get_session):
        """
        Test Case 5.7: Verify prediction request creates database entry.
        """
        # Arrange
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_prediction = MagicMock()
        mock_prediction.id = 123
        self.pipeline.engine = MagicMock()
        
        # Act
        result = self.pipeline.request_prediction()
        
        # Assert
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_get_debug_info(self):
        """
        Test Case 5.8: Verify debug information is correctly returned.
        """
        # Arrange
        self.pipeline.running = True
        self.pipeline.predictor_plugin = MagicMock()
        self.pipeline.feeder_plugin = MagicMock()
        self.pipeline.engine = MagicMock()
        
        with patch.object(self.pipeline, 'get_last_prediction_status', return_value='completed'):
            # Act
            debug_info = self.pipeline.get_debug_info()
            
            # Assert
            self.assertIn("pipeline_enabled", debug_info)
            self.assertIn("running", debug_info)
            self.assertIn("predictor_loaded", debug_info)
            self.assertIn("feeder_loaded", debug_info)
            self.assertTrue(debug_info["running"])
            self.assertTrue(debug_info["predictor_loaded"])
            self.assertTrue(debug_info["feeder_loaded"])

    def test_get_system_status(self):
        """
        Test Case 5.9: Verify system status reporting works correctly.
        """
        # Arrange
        with patch.object(self.pipeline, '_validate_system', return_value=True), \
             patch.object(self.pipeline, 'get_last_prediction_status', return_value='completed'):
            
            self.pipeline.running = True
            
            # Act
            status = self.pipeline.get_system_status()
            
            # Assert
            self.assertIn("system_ready", status)
            self.assertIn("pipeline_running", status)
            self.assertIn("last_prediction_status", status)
            self.assertTrue(status["system_ready"])
            self.assertTrue(status["pipeline_running"])

    def test_cleanup(self):
        """
        Test Case 5.10: Verify pipeline cleanup sets running to False.
        """
        # Arrange
        self.pipeline.running = True
        
        # Act
        self.pipeline.cleanup()
        
        # Assert
        self.assertFalse(self.pipeline.running)

if __name__ == '__main__':
    unittest.main()
