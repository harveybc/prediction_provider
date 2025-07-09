# Real Market Data Feeder Plugin

## Overview

The `RealFeederPlugin` is a sophisticated data feeder designed for the Prediction Provider system. It efficiently fetches real-time market data for EURUSD, S&P500, and VIX, with multi-timeframe support and optimized API call patterns to minimize costs when using paid data providers.

## Features

### ✅ **Complete Implementation**
- **Multi-timeframe data fetching**: Hourly, 15-minute, and 30-minute data in minimal API calls
- **EURUSD HLOC data**: Full Open, High, Low, Close data for main instrument
- **Correlated instruments**: S&P500 and VIX close prices
- **Multi-timeframe tick features**: Last 8 ticks of 15m and 30m before each hour
- **Automatic normalization**: Using training data min/max values from JSON
- **Custom date range support**: Start/end datetime parameters
- **Technical indicator buffer**: Additional previous ticks parameter for indicator windows
- **Validation system**: Compare generated data against historical CSV with configurable error margin

### ✅ **Generated Columns (30 total, excluding technical indicators)**

#### Base HLOC Data (4 columns)
- `OPEN`, `HIGH`, `LOW`, `CLOSE` - EURUSD hourly HLOC data

#### Price Relationships (4 columns)
- `BC-BO` - Body Close minus Body Open (Close - Open)
- `BH-BL` - Body High minus Body Low (High - Low)  
- `BH-BO` - Body High minus Body Open (High - Open)
- `BO-BL` - Body Open minus Body Low (Open - Low)

#### External Market Data (2 columns)
- `S&P500_Close` - S&P500 hourly close prices
- `vix_close` - VIX hourly close prices

#### Multi-timeframe Features (16 columns)
- `CLOSE_15m_tick_1` through `CLOSE_15m_tick_8` - Last 8 15-minute closes before each hour
- `CLOSE_30m_tick_1` through `CLOSE_30m_tick_8` - Last 8 30-minute closes before each hour

#### Time Features (3 columns)
- `day_of_month` - Day of month (1-31)
- `hour_of_day` - Hour of day (0-23)
- `day_of_week` - Day of week (0-6, Monday=0)

#### DateTime (1 column)
- `DATE_TIME` - Timestamp for each data point

## API and Usage

### Basic Usage

```python
from plugins_feeder.real_feeder import RealFeederPlugin

# Initialize the feeder
feeder = RealFeederPlugin()

# Fetch recent data (default: last 30 days)
data = feeder.fetch()

# Fetch data for specific period
data = feeder.fetch_data_for_period(
    start_date='2025-07-01 00:00:00',
    end_date='2025-07-07 23:59:59',
    additional_previous_ticks=50
)
```

### Configuration Parameters

```python
plugin_params = {
    "instrument": "EURUSD=X",                    # Main trading instrument
    "correlated_instruments": ["^GSPC", "^VIX"], # Additional instruments
    "n_batches": 1,                              # Processing batches
    "batch_size": 256,                           # Batch size
    "window_size": 256,                          # Window size
    "use_normalization_json": "examples/data/phase_3/phase_3_debug_out.json",  # Normalization file
    "target_column": "CLOSE",                    # Target column
    "additional_previous_ticks": 50,             # Extra ticks for technical indicators
    "error_tolerance": 0.001                     # Validation error tolerance
}
```

### Integration with Pipeline

```python
from plugins_pipeline.enhanced_pipeline import EnhancedPipelinePlugin

# Enhanced pipeline with real-time support
pipeline = EnhancedPipelinePlugin({
    "real_time_mode": True,
    "data_lookback_hours": 168,  # 1 week
    "additional_previous_ticks": 50,
    "prediction_interval": 600   # 10 minutes
})

# Initialize with real feeder
pipeline.initialize(predictor_plugin, feeder_plugin)
```

### Predictor Integration Pattern

```python
class PredictorPlugin:
    def get_data_requirements(self, prediction_time=None):
        """Define data requirements for prediction."""
        end_date = prediction_time or datetime.now()
        start_date = end_date - timedelta(hours=24)
        
        return {
            "start_date": start_date.strftime('%Y-%m-%d %H:%M:%S'),
            "end_date": end_date.strftime('%Y-%m-%d %H:%M:%S'),
            "additional_previous_ticks": 50
        }
    
    def predict_with_feeder(self, feeder_plugin, prediction_time=None):
        """Request specific data from feeder for prediction."""
        requirements = self.get_data_requirements(prediction_time)
        
        if hasattr(feeder_plugin, 'fetch_data_for_period'):
            data = feeder_plugin.fetch_data_for_period(**requirements)
        else:
            data = feeder_plugin.fetch()  # Fallback
        
        return self.predict_with_uncertainty(data)
```

## Data Flow and Efficiency

### Optimized API Call Pattern

The feeder minimizes API calls by:

1. **Single timeframe fetch per instrument**: One call each for hourly, 15m, 30m data
2. **Bulk date range requests**: Request entire date range + buffer in one call
3. **Efficient tick calculation**: Calculate all 8 ticks per timeframe from bulk data
4. **Timezone handling**: Automatic timezone normalization for comparisons

### Multi-timeframe Tick Calculation

For each hourly data point:
- **15-minute ticks**: Find last 8 15-minute closes before that hour
- **30-minute ticks**: Find last 8 30-minute closes before that hour
- **Fallback strategy**: Use hourly close if insufficient historical data

```python
# Example tick calculation for hour 2025-07-07 15:00:00
# CLOSE_15m_tick_1 = most recent 15m close before 15:00 (e.g., 14:45)
# CLOSE_15m_tick_2 = second most recent (e.g., 14:30)
# ...
# CLOSE_15m_tick_8 = eighth most recent (e.g., 12:30)
```

## Normalization System

### Min-Max Normalization

Uses training data ranges from `phase_3_debug_out.json`:

```python
normalized_value = (value - min_value) / (max_value - min_value)
```

### Example Normalization Ranges

```json
{
    "OPEN": {"min": 1.03553, "max": 1.60131},
    "HIGH": {"min": 1.03697, "max": 1.60384},
    "LOW": {"min": 1.03395, "max": 1.5992},
    "CLOSE": {"min": 1.03555, "max": 1.60139},
    "S&P500_Close": {"min": 676.530029, "max": 3386.149902},
    "vix_close": {"min": 9.140000343322754, "max": 82.69000244140625}
}
```

## Validation System

### Historical Data Comparison

```python
validation_results = feeder.validate_against_historical(
    generated_data=current_data,
    historical_csv="examples/data/phase_3/normalized_d4.csv"
)

# Results structure
{
    "validation_passed": True/False,
    "total_common_dates": 150,
    "tolerance": 0.001,
    "column_comparisons": {
        "OPEN": {
            "max_difference": 0.0005,
            "mean_difference": 0.0001,
            "within_tolerance": True
        }
    }
}
```

## Error Handling and Robustness

### Automatic Fallbacks

1. **Missing data**: Fill with zeros or hourly close values
2. **Timezone issues**: Automatic timezone normalization
3. **API failures**: Graceful degradation with warnings
4. **Insufficient historical data**: Use available data with warnings

### Logging and Monitoring

```python
import logging

# Comprehensive logging at INFO level
logger.info(f"Fetched {data.shape[0]} rows with {data.shape[1]} columns")
logger.info(f"Date range: {data['DATE_TIME'].min()} to {data['DATE_TIME'].max()}")
logger.warning(f"Missing column {col}, filling with zeros")
logger.error(f"Could not load normalization file: {e}")
```

## Testing and Validation

### Test Script

Run the comprehensive test suite:

```bash
cd /home/harveybc/Documents/GitHub/prediction_provider
python test_real_feeder.py
```

### Test Coverage

1. **Basic functionality**: Default data fetching
2. **Custom date ranges**: Specific period data fetching  
3. **Column validation**: All 30 required columns present
4. **Normalization check**: Values properly normalized
5. **Historical comparison**: Validation against known data
6. **Multi-timeframe verification**: Tick data generation

### Integration Examples

```bash
python example_real_feeder_integration.py
```

## Performance Considerations

### API Call Optimization

- **Bulk requests**: Fetch large date ranges in single calls
- **Caching strategy**: Reuse downloaded data for multiple predictions
- **Rate limiting**: Respect Yahoo Finance rate limits
- **Error recovery**: Retry logic for failed requests

### Memory Management

- **Streaming processing**: Process data in chunks for large date ranges
- **Selective columns**: Only keep required columns in memory
- **Data cleanup**: Remove intermediate DataFrames after processing

## Production Deployment

### Configuration for Production

```python
production_config = {
    "additional_previous_ticks": 100,  # More buffer for complex indicators
    "error_tolerance": 0.005,          # Higher tolerance for live data
    "use_normalization_json": "/path/to/production/normalization.json"
}
```

### Monitoring and Alerts

- **Data quality checks**: Validate data completeness and ranges
- **API response monitoring**: Track request success rates and latencies  
- **Prediction accuracy tracking**: Compare predictions with actual outcomes
- **System health metrics**: Memory usage, processing times, error rates

## Future Enhancements

### Planned Features

1. **Technical indicators integration**: Call exact code from other repo
2. **Multiple data providers**: Support for paid data feeds (Alpha Vantage, Quandl, etc.)
3. **Data caching system**: Local cache for frequently requested data
4. **Real-time streaming**: WebSocket connections for live data
5. **Advanced validation**: Statistical tests for data quality

### Integration Points

- **Technical indicators**: Will be calculated using exact code from the other repository
- **Extended validation**: More comprehensive comparison with historical data
- **Performance optimization**: Further API call reduction strategies
- **Error handling**: Enhanced recovery mechanisms for production use

## File Structure

```
prediction_provider/
├── plugins_feeder/
│   ├── real_feeder.py              # Main implementation
│   └── default_feeder.py           # Reference implementation
├── plugins_pipeline/
│   ├── enhanced_pipeline.py        # Enhanced pipeline with date range support
│   └── default_pipeline.py         # Original pipeline
├── examples/data/phase_3/
│   ├── phase_3_debug_out.json      # Normalization parameters
│   └── normalized_d4.csv           # Historical validation data
├── test_real_feeder.py             # Comprehensive test suite
└── example_real_feeder_integration.py  # Integration examples
```

## Support and Troubleshooting

### Common Issues

1. **Timezone errors**: Ensure all datetime objects are timezone-naive
2. **Missing data**: Check Yahoo Finance data availability for requested dates
3. **Normalization issues**: Verify normalization JSON file path and format
4. **API rate limits**: Implement delays between requests if needed

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enables detailed logging of all operations
```

This implementation provides a robust, efficient, and scalable foundation for real-time market data feeding in the Prediction Provider system.
