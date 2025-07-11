# RealFeederPlugin - Perfect Replicability Guide

## Overview
The `RealFeederPlugin` is fully isolated and designed for perfect replicability across different applications. All processing parameters are contained within the plugin's configuration, ensuring identical results when the same parameters are used.

## Key Features for Replicability
- ✅ **Fully Self-Contained**: All processing logic is inside the plugin
- ✅ **Config-Driven**: Every parameter is explicit and configurable
- ✅ **Save/Load Parameters**: Export and import exact configurations
- ✅ **No Hidden State**: No global variables or hidden dependencies
- ✅ **Deterministic Processing**: Same inputs + same config = same outputs

## Plugin Architecture
The plugin follows the standard plugin architecture where:
1. Plugin has default parameters (`DEFAULT_CONFIG`)
2. Main app merges plugin defaults with global config
3. Plugin uses final merged parameters (`self.params`)
4. All processing uses `self.params` for consistency

## Usage in Another Application

### Method 1: Direct Parameter Passing
```python
from plugins_feeder.real_feeder import RealFeederPlugin

# Define exact parameters for replicability
replication_config = {
    "stl_period": 24,
    "stl_window": 49,
    "stl_trend": 25,
    "use_stl": True,
    "use_wavelets": True,
    "wavelet_name": "db4",
    "wavelet_levels": 2,
    "use_multi_tapper": True,
    "mtm_window_len": 168,
    "normalize_features": True,
    # ... all other parameters
}

# Create plugin with exact parameters
plugin = RealFeederPlugin(config=replication_config)

# Use the plugin
data = plugin.load_data("2024-01-01 00:00:00", "2024-01-02 00:00:00")
```

### Method 2: Save/Load Configuration
```python
# In the original app - save the configuration
plugin = RealFeederPlugin(config=custom_params)
plugin.save_config("feeder_replication_config.json")

# In another app - load the exact configuration
plugin_replica = RealFeederPlugin.from_config_file("feeder_replication_config.json")

# Both plugins will produce identical results
data1 = plugin.load_data(start_date, end_date)
data2 = plugin_replica.load_data(start_date, end_date)
# data1 and data2 will be identical
```

### Method 3: Export Parameters for Documentation
```python
plugin = RealFeederPlugin()
final_params = plugin.get_config()

# Save for documentation/replication
with open("production_config.json", "w") as f:
    json.dump(final_params, f, indent=2)

# This file contains ALL parameters needed for replication
```

## Configuration Parameters

### Core Data Processing
- `instrument`: Main trading instrument (default: "EURUSD=X")
- `correlated_instruments`: Additional instruments for features
- `window_size`: Data window size (default: 256)
- `target_column`: Target column name (default: "CLOSE")

### STL Feature Generation
- `use_stl`: Enable STL decomposition (default: True)
- `stl_period`: STL seasonal period (default: 24)
- `stl_window`: STL window size (default: 49)
- `stl_trend`: STL trend component size (default: 25)

### Wavelet Features
- `use_wavelets`: Enable wavelet features (default: True)
- `wavelet_name`: Wavelet type (default: "db4")
- `wavelet_levels`: Decomposition levels (default: 2)
- `wavelet_mode`: Boundary condition (default: "symmetric")

### Multi-Taper Method (MTM)
- `use_multi_tapper`: Enable MTM features (default: True)
- `mtm_window_len`: MTM window length (default: 168)
- `mtm_time_bandwidth`: Time-bandwidth product (default: 5.0)
- `mtm_freq_bands`: Frequency bands for analysis

### Normalization & Validation
- `normalize_features`: Apply normalization (default: True)
- `use_normalization_json`: Normalization parameters file
- `validate_feature_count`: Validate expected feature count
- `strict_validation`: Strict validation mode

## Ensuring Perfect Replicability

### 1. Always Use Explicit Configuration
```python
# ❌ DON'T: Rely on defaults (may change)
plugin = RealFeederPlugin()

# ✅ DO: Use explicit configuration
explicit_config = {
    "stl_period": 24,
    "use_stl": True,
    "use_wavelets": True,
    # ... all critical parameters
}
plugin = RealFeederPlugin(config=explicit_config)
```

### 2. Save Configuration for Production
```python
# After testing/validation
plugin.save_config("production_feeder_config.json")

# In production
plugin = RealFeederPlugin.from_config_file("production_feeder_config.json")
```

### 3. Verify Feature Count and Names
```python
# Check expected features
expected_features = plugin.get_expected_features()
print(f"Plugin will generate {len(expected_features)} features")

# After processing
data = plugin.load_data(start_date, end_date)
assert len(data.columns) == len(expected_features), "Feature count mismatch"
```

### 4. Document Your Configuration
```python
# Get plugin info for documentation
info = plugin.get_info()
params = plugin.get_config()

documentation = {
    "plugin": info["name"],
    "version": info["version"],
    "configuration": params,
    "expected_features": plugin.get_expected_features(),
    "feature_count": len(plugin.get_expected_features())
}

with open("feeder_documentation.json", "w") as f:
    json.dump(documentation, f, indent=2)
```

## Integration Examples

### Example 1: Predictor App Integration
```python
# In predictor app
from plugins_feeder.real_feeder import RealFeederPlugin

# Load exact configuration used during training
feeder = RealFeederPlugin.from_config_file("training_feeder_config.json")

# Generate features with identical processing
features = feeder.load_data(prediction_start, prediction_end)

# Features will match training data preprocessing exactly
predictions = model.predict(features)
```

### Example 2: Backtesting App Integration
```python
# In backtesting app
feeder_config = {
    "stl_period": 24,
    "normalize_features": False,  # Use raw features for backtesting
    "validate_feature_count": True,
    # ... other parameters
}

feeder = RealFeederPlugin(config=feeder_config)

# Process historical data with same feature engineering
for date_range in backtest_periods:
    features = feeder.load_data(date_range.start, date_range.end)
    # Run backtest with these features
```

## Troubleshooting Replicability

### Check Parameter Differences
```python
# Compare two configurations
config1 = plugin1.get_config()
config2 = plugin2.get_config()

for key in config1:
    if config1[key] != config2.get(key):
        print(f"Difference in {key}: {config1[key]} vs {config2.get(key)}")
```

### Verify Deterministic Processing
```python
# Same plugin, same data, should produce identical results
data1 = plugin.load_data("2024-01-01 00:00:00", "2024-01-02 00:00:00")
data2 = plugin.load_data("2024-01-01 00:00:00", "2024-01-02 00:00:00")

assert data1.equals(data2), "Plugin processing is not deterministic"
```

## Best Practices

1. **Always save production configurations**: Don't rely on code defaults
2. **Version your configurations**: Include plugin version in config files
3. **Test replicability**: Verify same config produces same results
4. **Document critical parameters**: Especially STL, wavelet, and MTM settings
5. **Use explicit parameters**: Don't rely on calculated or derived values
6. **Validate feature consistency**: Check feature count and names match expectations

## Summary

The `RealFeederPlugin` provides perfect replicability through:
- Complete parameter isolation in `self.params`
- Save/load functionality for exact configuration reproduction
- Deterministic processing with no hidden state
- Comprehensive configuration covering all feature generation steps

By following this guide, any application can achieve identical feature generation results by using the same plugin configuration.
