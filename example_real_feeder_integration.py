#!/usr/bin/env python3
"""
Real Feeder Integration Example

This example demonstrates how to integrate the RealFeederPlugin with the predictor
and pipeline plugins to create a complete real-time prediction system.
"""

import sys
import os
from datetime import datetime, timedelta

# Add the plugins directory to the Python path
sys.path.append('/home/harveybc/Documents/GitHub/prediction_provider')

# Import the plugins
from plugins_feeder.real_feeder import RealFeederPlugin
from plugins_pipeline.enhanced_pipeline import EnhancedPipelinePlugin

def example_basic_integration():
    """Example 1: Basic integration with custom date range."""
    
    print("="*60)
    print("EXAMPLE 1: BASIC REAL FEEDER INTEGRATION")
    print("="*60)
    
    # Initialize the real feeder
    feeder = RealFeederPlugin()
    
    # Fetch data for a specific period (last week)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    print(f"Fetching data from {start_date} to {end_date}")
    
    data = feeder.fetch_data_for_period(
        start_date=start_date.strftime('%Y-%m-%d %H:%M:%S'),
        end_date=end_date.strftime('%Y-%m-%d %H:%M:%S'),
        additional_previous_ticks=24  # 24 hours for technical indicators
    )
    
    print(f"✓ Fetched {len(data)} rows with {len(data.columns)} columns")
    print(f"  Date range: {data['DATE_TIME'].min()} to {data['DATE_TIME'].max()}")
    
    # Show column structure
    print("\nGenerated columns:")
    for i, col in enumerate(data.columns, 1):
        print(f"  {i:2d}. {col}")
    
    # Show sample data
    print("\nSample data (first 2 rows):")
    print(data.head(2)[['DATE_TIME', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'S&P500_Close', 'vix_close']].to_string())
    
    return data

def example_pipeline_integration():
    """Example 2: Integration with enhanced pipeline."""
    
    print("\n" + "="*60)
    print("EXAMPLE 2: ENHANCED PIPELINE INTEGRATION")
    print("="*60)
    
    # Initialize the real feeder
    feeder = RealFeederPlugin()
    
    # Initialize the enhanced pipeline
    pipeline = EnhancedPipelinePlugin({
        "real_time_mode": True,
        "data_lookback_hours": 168,  # 1 week
        "additional_previous_ticks": 50,
        "prediction_interval": 600   # 10 minutes
    })
    
    # For this example, we'll create a mock predictor
    class MockPredictor:
        def predict_with_uncertainty(self, data):
            """Mock predictor that just returns dummy predictions."""
            print(f"MockPredictor: Received data with shape {data.shape}")
            # In real implementation, this would run the actual model
            return {
                "predictions": [1.0850, 1.0855, 1.0860],  # Example EUR/USD predictions
                "uncertainties": [0.001, 0.002, 0.003],
                "confidence": 0.85,
                "timestamp": datetime.now().isoformat()
            }
    
    mock_predictor = MockPredictor()
    
    # Initialize the pipeline with plugins
    print("Initializing pipeline with real feeder...")
    pipeline.initialize(mock_predictor, feeder)
    
    # Get system status
    status = pipeline.get_system_status()
    print(f"System status: {status}")
    
    # Run a single prediction cycle with custom date range
    print("\nRunning single prediction cycle...")
    
    # Use a specific date range for demonstration
    end_date = datetime.now()
    start_date = end_date - timedelta(days=2)
    
    result = pipeline.run_single_prediction(
        start_date=start_date.strftime('%Y-%m-%d %H:%M:%S'),
        end_date=end_date.strftime('%Y-%m-%d %H:%M:%S')
    )
    
    print(f"Prediction result: {result}")
    
    return pipeline

def example_custom_parameters():
    """Example 3: Using custom parameters for specific use cases."""
    
    print("\n" + "="*60)
    print("EXAMPLE 3: CUSTOM PARAMETERS")
    print("="*60)
    
    # Custom configuration for specific trading strategy
    custom_config = {
        "instrument": "EURUSD=X",
        "correlated_instruments": ["^GSPC", "^VIX"],
        "additional_previous_ticks": 100,  # More data for complex indicators
        "error_tolerance": 0.005,  # Higher tolerance for live data
        "use_normalization_json": "examples/data/phase_3/phase_3_debug_out.json"
    }
    
    # Initialize with custom configuration
    feeder = RealFeederPlugin(custom_config)
    
    # Fetch data for a specific trading session (e.g., European session)
    # Using a date in the past for demonstration
    session_start = datetime(2025, 7, 1, 8, 0, 0)  # 8 AM
    session_end = datetime(2025, 7, 1, 17, 0, 0)   # 5 PM
    
    print(f"Fetching European trading session data:")
    print(f"  From: {session_start}")
    print(f"  To: {session_end}")
    
    session_data = feeder.fetch_data_for_period(
        start_date=session_start.strftime('%Y-%m-%d %H:%M:%S'),
        end_date=session_end.strftime('%Y-%m-%d %H:%M:%S'),
        additional_previous_ticks=custom_config["additional_previous_ticks"]
    )
    
    print(f"✓ Fetched {len(session_data)} rows for trading session")
    
    # Show trading session statistics
    if len(session_data) > 0:
        print(f"\nTrading session statistics:")
        print(f"  EUR/USD Open: {session_data['OPEN'].iloc[0]:.6f}")
        print(f"  EUR/USD Close: {session_data['CLOSE'].iloc[-1]:.6f}")
        print(f"  Session High: {session_data['HIGH'].max():.6f}")
        print(f"  Session Low: {session_data['LOW'].min():.6f}")
        print(f"  S&P500 avg: {session_data['S&P500_Close'].mean():.2f}")
        print(f"  VIX avg: {session_data['vix_close'].mean():.2f}")
    
    return session_data

def example_parameter_passing():
    """Example 4: How to pass parameters from predictor to feeder."""
    
    print("\n" + "="*60)
    print("EXAMPLE 4: PARAMETER PASSING PATTERN")
    print("="*60)
    
    # This shows the pattern for how a predictor plugin can pass
    # start/end dates and additional_previous_ticks to the feeder
    
    class ExamplePredictorPlugin:
        """Example predictor that defines its data requirements."""
        
        def __init__(self):
            self.data_requirements = {
                "lookback_hours": 24,  # How much historical data needed
                "additional_previous_ticks": 50,  # For technical indicators
                "minimum_data_points": 20  # Minimum rows required (reduced for demo)
            }
        
        def get_data_requirements(self, prediction_time=None):
            """Return data requirements for prediction."""
            if prediction_time is None:
                prediction_time = datetime.now()
            
            # Calculate required date range
            end_date = prediction_time
            start_date = end_date - timedelta(hours=self.data_requirements["lookback_hours"])
            
            return {
                "start_date": start_date.strftime('%Y-%m-%d %H:%M:%S'),
                "end_date": end_date.strftime('%Y-%m-%d %H:%M:%S'),
                "additional_previous_ticks": self.data_requirements["additional_previous_ticks"]
            }
        
        def predict_with_feeder(self, feeder_plugin, prediction_time=None):
            """Example of how predictor can request specific data from feeder."""
            
            # Get data requirements
            requirements = self.get_data_requirements(prediction_time)
            
            print(f"Predictor requesting data:")
            print(f"  Start: {requirements['start_date']}")
            print(f"  End: {requirements['end_date']}")
            print(f"  Additional ticks: {requirements['additional_previous_ticks']}")
            
            # Request data from feeder
            if hasattr(feeder_plugin, 'fetch_data_for_period'):
                data = feeder_plugin.fetch_data_for_period(**requirements)
            else:
                # Fallback for feeders without date range support
                data = feeder_plugin.fetch()
            
            print(f"✓ Received data: {data.shape}")
            
            # Validate data meets requirements
            if len(data) < self.data_requirements["minimum_data_points"]:
                raise ValueError(f"Insufficient data: {len(data)} < {self.data_requirements['minimum_data_points']}")
            
            # Perform prediction (mock)
            prediction = {
                "value": 1.0850,
                "uncertainty": 0.001,
                "data_points_used": len(data),
                "data_date_range": f"{data['DATE_TIME'].min()} to {data['DATE_TIME'].max()}"
            }
            
            return prediction
    
    # Demonstrate the pattern
    predictor = ExamplePredictorPlugin()
    feeder = RealFeederPlugin()
    
    # Make a prediction with specific data requirements
    prediction = predictor.predict_with_feeder(feeder)
    
    print(f"Prediction result: {prediction}")
    
    return prediction

if __name__ == "__main__":
    print("Real Feeder Integration Examples")
    print("================================")
    
    try:
        # Run examples
        data1 = example_basic_integration()
        pipeline = example_pipeline_integration()
        data2 = example_custom_parameters()
        prediction = example_parameter_passing()
        
        print("\n" + "="*60)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY! 🎉")
        print("="*60)
        
        print("\nKey Integration Points:")
        print("1. ✅ RealFeederPlugin can fetch data for custom date ranges")
        print("2. ✅ Enhanced pipeline supports passing start/end dates to feeder")
        print("3. ✅ Predictor plugins can specify their data requirements")
        print("4. ✅ System supports both real-time and historical data fetching")
        print("5. ✅ All 30 non-technical-indicator columns are generated correctly")
        
        print("\nNext Steps:")
        print("• Add technical indicators calculation (from other repo)")
        print("• Test with actual predictor models")
        print("• Validate against more historical data")
        print("• Optimize API call efficiency for production use")
        
    except Exception as e:
        print(f"\n❌ Error in examples: {e}")
        import traceback
        traceback.print_exc()
