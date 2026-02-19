# Plugin Replicability Guide

## Overview

This guide explains how to create new plugins that are compatible with the Prediction Provider's plugin system. All plugins are loaded via Python entry points, ensuring a consistent interface.

## Plugin Interface Requirements

Every plugin must have:

```python
class MyPlugin:
    # Required: dict of parameter names → default values
    plugin_params = {
        "param_name": "default_value",
    }
    
    # Optional: list of param names for debug output
    plugin_debug_vars = ["param_name"]
    
    def __init__(self, config=None):
        self.params = self.plugin_params.copy()
        if config:
            self.set_params(**config)
    
    def set_params(self, **kwargs):
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value
```

## Plugin Types

### Feeder Plugin

Must implement:
- `fetch()` → `pd.DataFrame` — Return data with at least a datetime column and target column

Optional:
- `fetch_data_for_period(start_date, end_date, additional_previous_ticks)` — Date range support

### Predictor Plugin

Must implement at least one of:
- `predict_request(input_df: pd.DataFrame, request: dict)` → `dict` — For pipeline API integration
- `predict_with_uncertainty(input_data)` → `dict` — For scheduled predictions
- `predict(input_data)` → predictions — Basic prediction

### Pipeline Plugin

Must implement:
- `initialize(predictor_plugin, feeder_plugin)` — Wire plugins
- `run_request(request: dict)` → `dict` — Execute single prediction

Optional:
- `run()` — Main loop for scheduled predictions
- `get_system_status()` → `dict`

### Core Plugin

Must implement:
- `set_plugins(plugins: dict)` — Receive all loaded plugins
- `start()` — Start the server
- `stop()` — Stop the server

### Endpoint Plugin

Must implement:
- `register_routes(app: FastAPI)` — Register routes on the app

## Registering Entry Points

In `setup.py`:

```python
entry_points={
    'feeder.plugins': [
        'my_feeder=plugins_feeder.my_feeder:MyFeeder',
    ],
    'predictor.plugins': [
        'my_predictor=plugins_predictor.my_predictor:MyPredictor',
    ],
    'pipeline.plugins': [
        'my_pipeline=plugins_pipeline.my_pipeline:MyPipeline',
    ],
}
```

After adding, run:
```bash
pip install -e .
```

## Using Your Plugin

Via CLI:
```bash
prediction_provider --feeder_plugin my_feeder --my_feeder_param value
```

Via config file:
```json
{"feeder_plugin": "my_feeder", "my_feeder_param": "value"}
```

## Testing Your Plugin

```python
from app.plugin_loader import load_plugin

# Verify it loads
plugin_class, params = load_plugin('feeder.plugins', 'my_feeder')
instance = plugin_class({"my_feeder_param": "test"})

# Verify fetch works
df = instance.fetch()
assert df is not None and not df.empty
```

## Reproducibility

For reproducible results:
1. Use fixed random seeds (see `NoisyIdealPredictor.noise_seed`)
2. Pin data sources (use `data_source="file"` with fixed CSV)
3. Document all parameters and their effects
4. Include normalization parameters as JSON files
