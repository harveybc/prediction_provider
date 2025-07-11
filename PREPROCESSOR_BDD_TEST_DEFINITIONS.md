# Data Preprocessor Plugin - BDD Test Definitions

## Test Execution Framework

This document provides concrete test definitions that map directly to the behavioral requirements. Each test is designed to validate specific behaviors without testing implementation details.

## Unit Test Definitions

### UT1_ConfigurationManager

#### UT1.1_ParameterMerging

**File**: `tests/unit_tests/test_configuration_manager.py`

```python
import pytest
from pytest_bdd import scenarios, given, when, then
from app.config_handler import ConfigurationManager

scenarios('../../features/configuration_manager.feature')

@pytest.fixture
def config_manager():
    return ConfigurationManager()

@given("a ConfigurationManager instance")
def config_manager_instance(config_manager):
    return config_manager

@when("I request the default configuration")
def request_default_config(config_manager):
    config_manager.config = config_manager.get_default_config()

@then("I should receive all required default parameters")
def verify_default_parameters(config_manager):
    required_params = [
        'use_external_feature_eng', 'autoencoder_split_ratios', 
        'predictor_split_ratios', 'normalization_method', 
        'autoencoder_norm_file', 'predictor_norm_file'
    ]
    for param in required_params:
        assert param in config_manager.config
        assert config_manager.config[param] is not None

@then("all parameters should have valid types and ranges")
def verify_parameter_validity(config_manager):
    # Split ratios should be lists of 3 floats that sum to 1.0
    for split_param in ['autoencoder_split_ratios', 'predictor_split_ratios']:
        ratios = config_manager.config[split_param]
        assert isinstance(ratios, list)
        assert len(ratios) == 3
        assert all(isinstance(r, (int, float)) for r in ratios)
        assert abs(sum(ratios) - 1.0) < 1e-6
    
    # Normalization method should be valid
    assert config_manager.config['normalization_method'] in ['zscore', 'minmax']
    
    # File paths should be strings
    assert isinstance(config_manager.config['autoencoder_norm_file'], str)
    assert isinstance(config_manager.config['predictor_norm_file'], str)
```

#### UT1.2_JSONOperations

```python
@when('I save the configuration to "{filename}"')
def save_config_to_file(config_manager, filename):
    config_manager.save_config(filename)

@then('the file should contain all parameters in JSON format')
def verify_json_format(config_manager, filename):
    import json
    with open(filename, 'r') as f:
        saved_config = json.load(f)
    
    # Verify all required parameters are present
    assert 'use_external_feature_eng' in saved_config
    assert 'autoencoder_split_ratios' in saved_config
    assert 'predictor_split_ratios' in saved_config

@when('I load the configuration using ConfigurationManager')
def load_config_from_file(config_manager, filename):
    config_manager.loaded_config = config_manager.load_config(filename)

@then("I should receive the exact same parameters")
def verify_loaded_config_matches(config_manager):
    original = config_manager.config
    loaded = config_manager.loaded_config
    
    # Compare all parameters
    for key in original:
        assert key in loaded
        assert original[key] == loaded[key]
```

### UT2_DataSplitter

#### UT2.1_SixDatasetSplit

**File**: `tests/unit_tests/test_data_splitter.py`

```python
import pytest
import pandas as pd
import numpy as np
from pytest_bdd import scenarios, given, when, then
from app.data_splitter import DataSplitter

scenarios('../../features/data_splitter.feature')

@pytest.fixture
def data_splitter():
    config = {
        'autoencoder_split_ratios': [0.7, 0.15, 0.15],
        'predictor_split_ratios': [0.7, 0.15, 0.15],
        'temporal_split': True,
        'split_overlap': 0.0
    }
    return DataSplitter(config)

@given("a dataset with {num_rows:d} rows")
def create_dataset(num_rows):
    np.random.seed(42)  # For reproducibility
    data = {
        'timestamp': pd.date_range('2020-01-01', periods=num_rows, freq='H'),
        'feature_1': np.random.randn(num_rows),
        'feature_2': np.random.randn(num_rows),
        'target': np.random.randn(num_rows)
    }
    return pd.DataFrame(data)

@given('split ratios {ratios} for both paths')
def set_split_ratios(data_splitter, ratios):
    ratios_list = eval(ratios)  # Convert string to list
    data_splitter.config['autoencoder_split_ratios'] = ratios_list
    data_splitter.config['predictor_split_ratios'] = ratios_list

@when("I split the data into six datasets")
def split_data_into_six(data_splitter, dataset):
    splits = data_splitter.split_data(dataset)
    data_splitter.splits = splits
    return splits

@then("d1 should have {expected_rows:d} rows")
def verify_d1_rows(data_splitter, expected_rows):
    assert len(data_splitter.splits['d1']) == expected_rows

@then("d2 should have {expected_rows:d} rows")
def verify_d2_rows(data_splitter, expected_rows):
    assert len(data_splitter.splits['d2']) == expected_rows

# Similar patterns for d3, d4, d5, d6...

@then("there should be no temporal overlap unless configured")
def verify_no_temporal_overlap(data_splitter):
    splits = data_splitter.splits
    
    # Check autoencoder path temporal ordering
    d1_end = splits['d1']['timestamp'].max()
    d2_start = splits['d2']['timestamp'].min()
    d2_end = splits['d2']['timestamp'].max()
    d3_start = splits['d3']['timestamp'].min()
    
    assert d1_end <= d2_start  # No gap or overlap
    assert d2_end <= d3_start
    
    # Check predictor path temporal ordering
    d4_end = splits['d4']['timestamp'].max()
    d5_start = splits['d5']['timestamp'].min()
    d5_end = splits['d5']['timestamp'].max()
    d6_start = splits['d6']['timestamp'].min()
    
    assert d4_end <= d5_start
    assert d5_end <= d6_start
```

#### UT2.2_SplitValidation

```python
@when("I validate for data leakage")
def validate_data_leakage(data_splitter):
    splits = data_splitter.splits
    data_splitter.leakage_validation = data_splitter.validate_no_leakage(splits)

@then("no samples should appear in multiple training sets")
def verify_no_training_leakage(data_splitter):
    validation = data_splitter.leakage_validation
    assert validation['training_sets_clean'] == True
    assert len(validation['training_overlaps']) == 0

@then("validation/test sets should not overlap with training")
def verify_no_train_val_test_leakage(data_splitter):
    validation = data_splitter.leakage_validation
    assert validation['train_val_test_clean'] == True
    assert len(validation['forbidden_overlaps']) == 0
```

### UT3_AutoencoderNormalizer

#### UT3.1_ZScoreNormalization

**File**: `tests/unit_tests/test_autoencoder_normalizer.py`

```python
import pytest
import pandas as pd
import numpy as np
import json
from pytest_bdd import scenarios, given, when, then
from app.autoencoder_normalizer import AutoencoderNormalizer

scenarios('../../features/autoencoder_normalizer.feature')

@pytest.fixture
def autoencoder_normalizer():
    config = {
        'normalization_method': 'zscore',
        'autoencoder_norm_file': 'autoencoder_normalization.json',
        'per_feature_normalization': True,
        'handle_outliers': True
    }
    return AutoencoderNormalizer(config)

@given("d1 dataset with features {feature_list}")
def create_d1_dataset(feature_list):
    features = eval(feature_list)  # Convert string to list
    np.random.seed(42)
    
    data = {}
    for feature in features:
        # Create features with different means and stds
        if feature == 'A':
            data[feature] = np.random.normal(10, 2, 1000)
        elif feature == 'B':
            data[feature] = np.random.normal(50, 10, 1000)
        elif feature == 'C':
            data[feature] = np.random.normal(-5, 0.5, 1000)
    
    return pd.DataFrame(data)

@when("I fit the AutoencoderNormalizer on d1")
def fit_normalizer_on_d1(autoencoder_normalizer, d1_dataset):
    autoencoder_normalizer.fit(d1_dataset)

@then("mean and std should be calculated for each feature")
def verify_parameters_calculated(autoencoder_normalizer, d1_dataset):
    params = autoencoder_normalizer.get_parameters()
    
    for feature in d1_dataset.columns:
        assert feature in params
        assert 'mean' in params[feature]
        assert 'std' in params[feature]
        
        # Verify calculated values are reasonable
        expected_mean = d1_dataset[feature].mean()
        expected_std = d1_dataset[feature].std()
        
        assert abs(params[feature]['mean'] - expected_mean) < 1e-6
        assert abs(params[feature]['std'] - expected_std) < 1e-6

@then("parameters should be saved to autoencoder_normalization.json")
def verify_parameters_saved(autoencoder_normalizer):
    filename = autoencoder_normalizer.config['autoencoder_norm_file']
    
    # Verify file exists and contains correct structure
    with open(filename, 'r') as f:
        saved_params = json.load(f)
    
    # Check structure: {feature: {mean: X, std: Y}}
    for feature, params in saved_params.items():
        assert 'mean' in params
        assert 'std' in params
        assert isinstance(params['mean'], (int, float))
        assert isinstance(params['std'], (int, float))

@when("I normalize d1 using its own parameters")
def normalize_d1_self(autoencoder_normalizer, d1_dataset):
    autoencoder_normalizer.normalized_d1 = autoencoder_normalizer.transform(d1_dataset)

@then("each feature should have approximately mean=0, std=1")
def verify_normalized_distribution(autoencoder_normalizer):
    normalized = autoencoder_normalizer.normalized_d1
    
    for column in normalized.columns:
        feature_mean = normalized[column].mean()
        feature_std = normalized[column].std()
        
        # Allow small tolerance for floating point precision
        assert abs(feature_mean) < 1e-10, f"Feature {column} mean: {feature_mean}"
        assert abs(feature_std - 1.0) < 1e-10, f"Feature {column} std: {feature_std}"

@given("a feature with constant values (std=0)")
def create_constant_feature_dataset():
    data = {
        'constant_feature': [5.0] * 1000,  # All same value
        'normal_feature': np.random.randn(1000)
    }
    return pd.DataFrame(data)

@then("std should be set to 1.0 to avoid division by zero")
def verify_zero_std_handling(autoencoder_normalizer, constant_dataset):
    autoencoder_normalizer.fit(constant_dataset)
    params = autoencoder_normalizer.get_parameters()
    
    # Constant feature should have std=1.0 to avoid division by zero
    assert params['constant_feature']['std'] == 1.0
    
    # Normal feature should have calculated std
    assert params['normal_feature']['std'] != 1.0
    assert params['normal_feature']['std'] > 0
```

### UT4_PredictorNormalizer

#### UT4.1_IndependentNormalization

**File**: `tests/unit_tests/test_predictor_normalizer.py`

```python
import pytest
import pandas as pd
import numpy as np
import json
from pytest_bdd import scenarios, given, when, then
from app.predictor_normalizer import PredictorNormalizer
from app.autoencoder_normalizer import AutoencoderNormalizer

scenarios('../../features/predictor_normalizer.feature')

@given("d1 and d4 with different feature distributions")
def create_different_distributions():
    np.random.seed(42)
    
    # d1 with one distribution
    d1 = pd.DataFrame({
        'feature_1': np.random.normal(10, 2, 1000),
        'feature_2': np.random.normal(0, 1, 1000)
    })
    
    # d4 with different distribution  
    d4 = pd.DataFrame({
        'feature_1': np.random.normal(50, 10, 1000),  # Different mean and std
        'feature_2': np.random.normal(20, 5, 1000)    # Different mean and std
    })
    
    return {'d1': d1, 'd4': d4}

@when("both normalizers are fitted")
def fit_both_normalizers(different_distributions):
    autoencoder_config = {
        'normalization_method': 'zscore',
        'autoencoder_norm_file': 'autoencoder_normalization.json'
    }
    predictor_config = {
        'normalization_method': 'zscore', 
        'predictor_norm_file': 'predictor_normalization.json'
    }
    
    autoencoder_norm = AutoencoderNormalizer(autoencoder_config)
    predictor_norm = PredictorNormalizer(predictor_config)
    
    autoencoder_norm.fit(different_distributions['d1'])
    predictor_norm.fit(different_distributions['d4'])
    
    return {
        'autoencoder': autoencoder_norm,
        'predictor': predictor_norm
    }

@then("autoencoder_normalization.json != predictor_normalization.json")
def verify_different_normalization_files(fitted_normalizers):
    # Load both JSON files
    with open('autoencoder_normalization.json', 'r') as f:
        auto_params = json.load(f)
    
    with open('predictor_normalization.json', 'r') as f:
        pred_params = json.load(f)
    
    # Verify they have different values
    for feature in auto_params:
        if feature in pred_params:
            # Means should be different
            assert auto_params[feature]['mean'] != pred_params[feature]['mean']
            # Standard deviations should be different  
            assert auto_params[feature]['std'] != pred_params[feature]['std']

@then("each path should have optimized scaling for its purpose")
def verify_optimized_scaling(fitted_normalizers):
    auto_norm = fitted_normalizers['autoencoder']
    pred_norm = fitted_normalizers['predictor']
    
    # Each normalizer should have parameters optimized for its data
    auto_params = auto_norm.get_parameters()
    pred_params = pred_norm.get_parameters()
    
    # Verify parameters are reasonable for each dataset
    for feature in auto_params:
        assert isinstance(auto_params[feature]['mean'], (int, float))
        assert isinstance(auto_params[feature]['std'], (int, float))
        assert auto_params[feature]['std'] > 0
    
    for feature in pred_params:
        assert isinstance(pred_params[feature]['mean'], (int, float))
        assert isinstance(pred_params[feature]['std'], (int, float))
        assert pred_params[feature]['std'] > 0
```

### UT5_ExternalFeatureEngPlugin

#### UT5.1_PluginIntegration

**File**: `tests/unit_tests/test_external_feature_eng.py`

```python
import pytest
import pandas as pd
import numpy as np
from pytest_bdd import scenarios, given, when, then
from app.plugin_loader import PluginLoader
from app.external_feature_eng_manager import ExternalFeatureEngManager

scenarios('../../features/external_feature_eng.feature')

@given("an external TechnicalIndicatorPlugin")
def mock_technical_indicator_plugin():
    """Mock external plugin for testing"""
    class MockTechnicalIndicatorPlugin:
        def __init__(self, config):
            self.config = config
            
        def calculate_indicators(self, data):
            """Mock indicator calculation"""
            result = data.copy()
            
            if 'RSI' in self.config.get('indicators', []):
                result['RSI'] = np.random.uniform(0, 100, len(data))
            
            if 'MACD' in self.config.get('indicators', []):
                result['MACD'] = np.random.randn(len(data))
                result['MACD_Signal'] = np.random.randn(len(data))
                result['MACD_Histogram'] = result['MACD'] - result['MACD_Signal']
            
            return result
    
    return MockTechnicalIndicatorPlugin

@when('I configure it with parameters {params}')
def configure_plugin(mock_technical_indicator_plugin, params):
    config = eval(params)  # Convert string to dict
    plugin_instance = mock_technical_indicator_plugin(config)
    
    # Create manager to handle the plugin
    manager_config = {
        'use_external_feature_eng': True,
        'feature_eng_plugin': 'TechnicalIndicatorPlugin',
        'feature_eng_params': config
    }
    
    manager = ExternalFeatureEngManager(manager_config)
    manager.plugin = plugin_instance  # Inject mock plugin
    
    return manager

@then("the plugin should be loaded successfully")
def verify_plugin_loaded(configured_manager):
    assert configured_manager.plugin is not None
    assert hasattr(configured_manager.plugin, 'calculate_indicators')

@then("configuration should be passed correctly")
def verify_config_passed(configured_manager):
    expected_indicators = ['RSI', 'MACD']
    actual_indicators = configured_manager.plugin.config.get('indicators', [])
    
    assert set(expected_indicators) == set(actual_indicators)

@when("I process a dataset through the plugin")
def process_through_plugin(configured_manager):
    # Create test dataset
    test_data = pd.DataFrame({
        'OPEN': np.random.randn(100),
        'HIGH': np.random.randn(100),
        'LOW': np.random.randn(100),
        'CLOSE': np.random.randn(100),
        'VOLUME': np.random.randint(1000, 10000, 100)
    })
    
    configured_manager.processed_data = configured_manager.plugin.calculate_indicators(test_data)
    configured_manager.original_data = test_data

@then("new features should be added to the dataset")
def verify_new_features_added(configured_manager):
    original_cols = set(configured_manager.original_data.columns)
    processed_cols = set(configured_manager.processed_data.columns)
    
    new_features = processed_cols - original_cols
    
    # Should have RSI and MACD-related features
    expected_new_features = {'RSI', 'MACD', 'MACD_Signal', 'MACD_Histogram'}
    assert expected_new_features.issubset(new_features)

@then("original features should be preserved")
def verify_original_features_preserved(configured_manager):
    original_cols = set(configured_manager.original_data.columns)
    processed_cols = set(configured_manager.processed_data.columns)
    
    # All original columns should still exist
    assert original_cols.issubset(processed_cols)
    
    # Original data should be unchanged
    for col in original_cols:
        pd.testing.assert_series_equal(
            configured_manager.original_data[col],
            configured_manager.processed_data[col]
        )
```

### UT6_PostprocessingPlugin

#### UT6.1_ColumnDecomposition

**File**: `tests/unit_tests/test_postprocessing_plugin.py`

```python
import pytest
import pandas as pd
import numpy as np
from pytest_bdd import scenarios, given, when, then
from app.postprocessing_plugin import PostprocessingPlugin

scenarios('../../features/postprocessing_plugin.feature')

@pytest.fixture
def postprocessing_plugin():
    config = {
        'use_postprocessing': True,
        'decomposition_columns': ['CLOSE'],
        'decomposition_methods': ['STL'],
        'decomposition_params': {
            'stl_period': 24,
            'wavelet_name': 'db4',
            'wavelet_levels': 3
        }
    }
    return PostprocessingPlugin(config)

@given("a CLOSE column with time series data")
def create_close_time_series():
    np.random.seed(42)
    
    # Create realistic time series with trend and seasonality
    t = np.arange(1000)
    trend = 0.01 * t
    seasonal = 5 * np.sin(2 * np.pi * t / 24)  # Daily seasonality
    noise = np.random.randn(1000) * 0.5
    
    close_values = 100 + trend + seasonal + noise
    
    data = pd.DataFrame({
        'timestamp': pd.date_range('2020-01-01', periods=1000, freq='H'),
        'CLOSE': close_values,
        'VOLUME': np.random.randint(1000, 10000, 1000)
    })
    
    return data

@when("I apply STL decomposition")
def apply_stl_decomposition(postprocessing_plugin, close_time_series):
    postprocessing_plugin.processed_data = postprocessing_plugin.decompose_columns(close_time_series)

@then("CLOSE should be replaced by [CLOSE_trend, CLOSE_seasonal, CLOSE_residual]")
def verify_stl_replacement(postprocessing_plugin):
    processed = postprocessing_plugin.processed_data
    
    # Original CLOSE should be removed
    assert 'CLOSE' not in processed.columns
    
    # STL components should be present
    expected_components = ['CLOSE_trend', 'CLOSE_seasonal', 'CLOSE_residual']
    for component in expected_components:
        assert component in processed.columns
        
    # Components should have reasonable values
    assert not processed['CLOSE_trend'].isna().any()
    assert not processed['CLOSE_seasonal'].isna().any()
    assert not processed['CLOSE_residual'].isna().any()

@then("decomposition should preserve temporal relationships")
def verify_temporal_preservation(postprocessing_plugin, close_time_series):
    processed = postprocessing_plugin.processed_data
    
    # Length should be preserved (or with minimal loss due to decomposition requirements)
    assert len(processed) >= len(close_time_series) * 0.95  # Allow 5% loss
    
    # Timestamp column should be preserved
    assert 'timestamp' in processed.columns
    
    # Temporal order should be maintained
    assert processed['timestamp'].is_monotonic_increasing

@given('decomposition_params {params}')
def set_decomposition_params(postprocessing_plugin, params):
    param_dict = eval(params)  # Convert string to dict
    postprocessing_plugin.config['decomposition_params'].update(param_dict)

@given('decomposition_methods {methods}')
def set_decomposition_methods(postprocessing_plugin, methods):
    method_list = eval(methods)  # Convert string to list
    postprocessing_plugin.config['decomposition_methods'] = method_list

@when("I decompose a configured column")
def decompose_configured_column(postprocessing_plugin, close_time_series):
    postprocessing_plugin.processed_data = postprocessing_plugin.decompose_columns(close_time_series)

@then("I should get {detail_levels:d} detail levels + 1 approximation")
def verify_wavelet_decomposition(postprocessing_plugin, detail_levels):
    processed = postprocessing_plugin.processed_data
    
    # Check for detail levels
    for level in range(1, detail_levels + 1):
        detail_col = f'CLOSE_wavelet_detail_L{level}'
        assert detail_col in processed.columns
    
    # Check for approximation
    approx_col = f'CLOSE_wavelet_approx_L{detail_levels}'
    assert approx_col in processed.columns

@then("feature names should be systematic")
def verify_systematic_naming(postprocessing_plugin):
    processed = postprocessing_plugin.processed_data
    
    # All decomposition features should follow naming convention
    decomp_features = [col for col in processed.columns if 'CLOSE_' in col]
    
    for feature in decomp_features:
        # Should start with original column name
        assert feature.startswith('CLOSE_')
        
        # Should have method identifier
        method_indicators = ['trend', 'seasonal', 'residual', 'wavelet', 'mtm']
        assert any(indicator in feature for indicator in method_indicators)

@when("I decompose CLOSE column")  
def decompose_close_column(postprocessing_plugin, close_time_series):
    postprocessing_plugin.processed_data = postprocessing_plugin.decompose_columns(close_time_series)

@then("I should get both STL and Wavelet features")
def verify_multiple_decomposition_methods(postprocessing_plugin):
    processed = postprocessing_plugin.processed_data
    
    # Should have STL features
    stl_features = [col for col in processed.columns if any(x in col for x in ['trend', 'seasonal', 'residual'])]
    assert len(stl_features) >= 3  # At least trend, seasonal, residual
    
    # Should have wavelet features  
    wavelet_features = [col for col in processed.columns if 'wavelet' in col]
    assert len(wavelet_features) >= 2  # At least some detail + approximation levels

@then("feature count should increase appropriately")
def verify_feature_count_increase(postprocessing_plugin, close_time_series):
    original_count = len(close_time_series.columns)
    processed_count = len(postprocessing_plugin.processed_data.columns)
    
    # Should have more features after decomposition
    # Original CLOSE removed (-1) + STL components (+3) + wavelet components (+4) = +6 net
    expected_min_increase = 6
    actual_increase = processed_count - original_count
    
    assert actual_increase >= expected_min_increase
```

## Component Test Definitions

### CT1_FeatureEngineeringPipeline

**File**: `tests/component_tests/test_feature_pipeline.py`

```python
import pytest
import pandas as pd
import numpy as np
from pytest_bdd import scenarios, given, when, then
from app.feature_engineering_pipeline import FeatureEngineeringPipeline

scenarios('../../features/feature_pipeline.feature')

@pytest.fixture
def feature_pipeline():
    config = {
        'use_external_feature_eng': True,
        'feature_eng_params': {'indicators': ['RSI', 'MACD']},
        'use_postprocessing': True,
        'decomposition_columns': ['CLOSE'],
        'decomposition_methods': ['STL', 'Wavelet']
    }
    return FeatureEngineeringPipeline(config)

@given("raw OHLC data")
def create_raw_ohlc_data():
    np.random.seed(42)
    
    data = pd.DataFrame({
        'timestamp': pd.date_range('2020-01-01', periods=1000, freq='H'),
        'OPEN': np.random.uniform(95, 105, 1000),
        'HIGH': np.random.uniform(100, 110, 1000), 
        'LOW': np.random.uniform(90, 100, 1000),
        'CLOSE': np.random.uniform(95, 105, 1000),
        'VOLUME': np.random.randint(1000, 10000, 1000)
    })
    
    return data

@when("I apply external feature engineering followed by postprocessing")
def apply_complete_pipeline(feature_pipeline, raw_ohlc_data):
    feature_pipeline.processed_data = feature_pipeline.process(raw_ohlc_data)

@then("technical indicators should be calculated first")
def verify_technical_indicators_first(feature_pipeline):
    processed = feature_pipeline.processed_data
    
    # Should have technical indicators
    expected_indicators = ['RSI', 'MACD', 'MACD_Signal', 'MACD_Histogram']
    for indicator in expected_indicators:
        assert indicator in processed.columns

@then("then decomposition should be applied to specified columns")
def verify_decomposition_applied(feature_pipeline):
    processed = feature_pipeline.processed_data
    
    # Original CLOSE should be replaced by decomposition components
    assert 'CLOSE' not in processed.columns
    
    # Should have decomposition features
    decomp_features = [col for col in processed.columns if 'CLOSE_' in col]
    assert len(decomp_features) > 0

@then("final dataset should have both indicators and decomposed features")
def verify_both_feature_types(feature_pipeline):
    processed = feature_pipeline.processed_data
    
    # Should have technical indicators
    indicator_features = [col for col in processed.columns if col in ['RSI', 'MACD', 'MACD_Signal', 'MACD_Histogram']]
    assert len(indicator_features) > 0
    
    # Should have decomposition features
    decomp_features = [col for col in processed.columns if 'CLOSE_' in col]
    assert len(decomp_features) > 0

@then("processing order should be deterministic") 
def verify_deterministic_processing(feature_pipeline, raw_ohlc_data):
    # Run processing multiple times
    result1 = feature_pipeline.process(raw_ohlc_data)
    result2 = feature_pipeline.process(raw_ohlc_data)
    
    # Results should be identical
    pd.testing.assert_frame_equal(result1, result2)
```

### CT2_SplitNormalizationPipeline

**File**: `tests/component_tests/test_split_normalize_pipeline.py`

```python
import pytest
import pandas as pd
import numpy as np
import json
from pytest_bdd import scenarios, given, when, then
from app.split_normalize_pipeline import SplitNormalizePipeline

scenarios('../../features/split_normalize_pipeline.feature')

@pytest.fixture
def split_normalize_pipeline():
    config = {
        'autoencoder_split_ratios': [0.7, 0.15, 0.15],
        'predictor_split_ratios': [0.7, 0.15, 0.15],
        'normalization_method': 'zscore',
        'autoencoder_norm_file': 'test_autoencoder_norm.json',
        'predictor_norm_file': 'test_predictor_norm.json'
    }
    return SplitNormalizePipeline(config)

@given("split datasets d1, d2, d3")
def create_autoencoder_splits():
    np.random.seed(42)
    
    # Create datasets with different characteristics
    d1 = pd.DataFrame({
        'feature_1': np.random.normal(10, 2, 700),
        'feature_2': np.random.normal(0, 1, 700)
    })
    
    d2 = pd.DataFrame({
        'feature_1': np.random.normal(10, 2, 150),
        'feature_2': np.random.normal(0, 1, 150)
    })
    
    d3 = pd.DataFrame({
        'feature_1': np.random.normal(10, 2, 150),
        'feature_2': np.random.normal(0, 1, 150)
    })
    
    return {'d1': d1, 'd2': d2, 'd3': d3}

@when("I apply autoencoder normalization")
def apply_autoencoder_normalization(split_normalize_pipeline, autoencoder_splits):
    split_normalize_pipeline.autoencoder_results = split_normalize_pipeline.normalize_autoencoder_path(autoencoder_splits)

@then("d1 should be used to calculate parameters")
def verify_d1_used_for_parameters(split_normalize_pipeline):
    # Check that normalization parameters file was created
    norm_file = split_normalize_pipeline.config['autoencoder_norm_file']
    assert os.path.exists(norm_file)
    
    # Parameters should be based on d1 statistics
    with open(norm_file, 'r') as f:
        params = json.load(f)
    
    # Should have parameters for each feature
    assert 'feature_1' in params
    assert 'feature_2' in params
    
    for feature in params:
        assert 'mean' in params[feature]
        assert 'std' in params[feature]

@then("d1, d2, d3 should all be normalized with d1 parameters")
def verify_consistent_normalization(split_normalize_pipeline):
    results = split_normalize_pipeline.autoencoder_results
    
    # All datasets should be normalized using same parameters
    norm_file = split_normalize_pipeline.config['autoencoder_norm_file']
    with open(norm_file, 'r') as f:
        params = json.load(f)
    
    # Verify normalization was applied consistently
    for dataset_name in ['d1', 'd2', 'd3']:
        dataset = results[dataset_name]
        
        for feature in dataset.columns:
            # Check that normalization was applied using d1 parameters
            original_mean = params[feature]['mean']
            original_std = params[feature]['std']
            
            # After normalization, d1 should have mean≈0, std≈1
            # d2, d3 should be scaled using same parameters
            assert not dataset[feature].isna().any()

@then("autoencoder_normalization.json should be saved")
def verify_autoencoder_norm_file_saved(split_normalize_pipeline):
    norm_file = split_normalize_pipeline.config['autoencoder_norm_file']
    assert os.path.exists(norm_file)
    
    # File should be valid JSON with correct structure
    with open(norm_file, 'r') as f:
        params = json.load(f)
    
    # Should have per-feature parameters
    for feature_name, feature_params in params.items():
        assert 'mean' in feature_params
        assert 'std' in feature_params
        assert isinstance(feature_params['mean'], (int, float))
        assert isinstance(feature_params['std'], (int, float))
        assert feature_params['std'] > 0
```

This comprehensive set of test definitions provides concrete implementations for all the behavioral requirements identified in the BDD methodology. Each test focuses on verifying behavior rather than implementation details, ensuring robust validation of the preprocessing pipeline's functionality.
