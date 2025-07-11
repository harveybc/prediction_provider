# Data Preprocessor Plugin - Implementation Architecture

## Overview

This document defines the hierarchical component architecture for implementing the Data Preprocessor Plugin, following the same modern structure as the prediction_provider repo. The implementation follows the BDD test-driven approach with components organized in dependency order.

## Project Structure

```
prediction_provider/
├── app/
│   ├── __init__.py
│   ├── main.py                          # Main application entry point
│   ├── cli.py                           # Command line interface
│   ├── config.py                        # Global configuration constants
│   ├── config_handler.py                # Configuration loading and validation
│   ├── config_merger.py                 # Configuration merging logic
│   ├── plugin_loader.py                 # Plugin loading and initialization
│   │
│   ├── data_preprocessor_plugin.py      # Main preprocessor plugin
│   ├── configuration_manager.py         # Level 1: Core configuration
│   ├── external_feature_eng_manager.py  # Level 2: External plugin management
│   ├── postprocessing_plugin.py         # Level 2: Column decomposition
│   ├── data_splitter.py                 # Level 2: Six-dataset splitting
│   ├── autoencoder_normalizer.py        # Level 3: Autoencoder normalization
│   ├── predictor_normalizer.py          # Level 3: Predictor normalization  
│   ├── validation_manager.py            # Level 4: Validation and QA
│   │
│   └── utils/
│       ├── __init__.py
│       ├── json_utils.py                # JSON file operations
│       ├── data_utils.py                # Data manipulation utilities
│       ├── logging_utils.py             # Logging configuration
│       └── validation_utils.py          # Common validation functions
│
├── preprocessor_plugins/
│   ├── __init__.py
│   └── data_preprocessor.py             # Main plugin implementation
│
├── external_plugins/
│   ├── __init__.py
│   ├── technical_indicator_plugin.py    # External feature engineering
│   └── decomposition_plugin.py          # External postprocessing
│
├── tests/
│   ├── __init__.py
│   ├── unit_tests/
│   │   ├── test_configuration_manager.py
│   │   ├── test_data_splitter.py
│   │   ├── test_autoencoder_normalizer.py
│   │   ├── test_predictor_normalizer.py
│   │   ├── test_external_feature_eng.py
│   │   └── test_postprocessing_plugin.py
│   │
│   ├── component_tests/
│   │   ├── test_feature_pipeline.py
│   │   ├── test_split_normalize_pipeline.py
│   │   └── test_configuration_integration.py
│   │
│   ├── integration_tests/
│   │   ├── test_end_to_end_pipeline.py
│   │   ├── test_plugin_interoperability.py
│   │   └── test_data_quality_validation.py
│   │
│   ├── system_tests/
│   │   ├── test_performance_scalability.py
│   │   └── test_error_handling_recovery.py
│   │
│   └── features/
│       ├── configuration_manager.feature
│       ├── data_splitter.feature
│       ├── autoencoder_normalizer.feature
│       ├── predictor_normalizer.feature
│       ├── external_feature_eng.feature
│       ├── postprocessing_plugin.feature
│       ├── feature_pipeline.feature
│       └── split_normalize_pipeline.feature
│
├── examples/
│   ├── data/
│   │   ├── sample_input.csv
│   │   ├── autoencoder_normalization.json
│   │   └── predictor_normalization.json
│   │
│   ├── config/
│   │   ├── default_preprocessing_config.json
│   │   └── production_preprocessing_config.json
│   │
│   └── scripts/
│       ├── run_preprocessing.py
│       └── validate_output.py
│
├── docs/
│   ├── PREPROCESSOR_BDD_DESIGN.md
│   ├── PREPROCESSOR_BDD_TEST_PLAN.md
│   ├── PREPROCESSOR_BDD_TEST_DEFINITIONS.md
│   ├── PREPROCESSOR_IMPLEMENTATION_ARCHITECTURE.md
│   └── API_REFERENCE.md
│
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Component Hierarchy and Implementation Order

### Phase 1: Foundation Components (Level 1)

#### 1.1 ConfigurationManager (`app/configuration_manager.py`)

**Dependencies**: None (foundational)
**Purpose**: Manage all configuration parameters with validation and persistence

```python
class ConfigurationManager:
    """
    Manages configuration parameters for the data preprocessor plugin.
    Provides validation, merging, and persistence capabilities.
    """
    
    DEFAULT_CONFIG = {
        # External Feature Engineering
        "use_external_feature_eng": True,
        "feature_eng_plugin": "TechnicalIndicatorPlugin",
        "feature_eng_params": {
            "indicators": ["RSI", "MACD", "EMA", "Bollinger"],
            "timeframes": [1, 5, 15, 30],
        },
        
        # Postprocessing Configuration
        "use_postprocessing": True,
        "postprocessing_plugin": "DecompositionPlugin",
        "decomposition_columns": ["CLOSE", "VOLUME"],
        "decomposition_methods": ["STL", "Wavelet", "MTM"],
        "decomposition_params": {
            "stl_period": 24,
            "wavelet_name": "db4",
            "wavelet_levels": 3,
            "mtm_window": 168
        },
        
        # Data Splitting Configuration
        "autoencoder_split_ratios": [0.7, 0.15, 0.15],
        "predictor_split_ratios": [0.7, 0.15, 0.15],
        "temporal_split": True,
        "split_overlap": 0.1,
        
        # Normalization Configuration
        "normalization_method": "zscore",
        "per_feature_normalization": True,
        "autoencoder_norm_file": "autoencoder_normalization.json",
        "predictor_norm_file": "predictor_normalization.json",
        "handle_outliers": True,
        "outlier_method": "iqr",
        
        # Validation Configuration
        "validate_splits": True,
        "validate_normalization": True,
        "check_data_leakage": True,
        "min_samples_per_split": 100,
        
        # Output Configuration
        "output_format": "csv",
        "save_metadata": True,
        "output_precision": 6,
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize with plugin-specific default parameters."""
        self.params = self.DEFAULT_CONFIG.copy()
        if config:
            self.params.update(config)
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        # Validate split ratios sum to 1.0
        for split_key in ['autoencoder_split_ratios', 'predictor_split_ratios']:
            ratios = self.params[split_key]
            if abs(sum(ratios) - 1.0) > 1e-6:
                raise ValueError(f"{split_key} must sum to 1.0, got {sum(ratios)}")
        
        # Validate normalization method
        if self.params['normalization_method'] not in ['zscore', 'minmax']:
            raise ValueError("normalization_method must be 'zscore' or 'minmax'")
        
        # Validate minimum samples
        if self.params['min_samples_per_split'] < 1:
            raise ValueError("min_samples_per_split must be positive")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.params.copy()
    
    def save_config(self, filepath: str) -> None:
        """Save configuration to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.params, f, indent=2)
    
    def load_config(self, filepath: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        with open(filepath, 'r') as f:
            return json.load(f)
    
    @classmethod
    def from_config_file(cls, filepath: str) -> 'ConfigurationManager':
        """Create instance from configuration file."""
        with open(filepath, 'r') as f:
            config = json.load(f)
        return cls(config)
```

**Tests to implement**: `tests/unit_tests/test_configuration_manager.py`
- Parameter merging behavior
- Configuration validation
- JSON persistence operations
- Error handling for invalid configurations

### Phase 2: Processing Components (Level 2)

#### 2.1 ExternalFeatureEngManager (`app/external_feature_eng_manager.py`)

**Dependencies**: ConfigurationManager
**Purpose**: Manage external feature engineering plugins

```python
class ExternalFeatureEngManager:
    """
    Manages external feature engineering plugins.
    Handles plugin loading, configuration, and execution.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration parameters."""
        self.params = config
        self.plugin = None
        self._load_plugin()
    
    def _load_plugin(self) -> None:
        """Load the specified external plugin."""
        if not self.params.get('use_external_feature_eng', False):
            return
        
        plugin_name = self.params.get('feature_eng_plugin')
        plugin_params = self.params.get('feature_eng_params', {})
        
        # Use plugin loader to load external plugin
        from app.plugin_loader import PluginLoader
        loader = PluginLoader()
        self.plugin = loader.load_external_plugin(plugin_name, plugin_params)
    
    def process_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply external feature engineering to data."""
        if self.plugin is None:
            return data
        
        return self.plugin.calculate_indicators(data)
    
    def get_info(self) -> Dict[str, Any]:
        """Get information about loaded plugin."""
        if self.plugin is None:
            return {"status": "No external plugin loaded"}
        
        return {
            "plugin_name": self.params.get('feature_eng_plugin'),
            "plugin_params": self.params.get('feature_eng_params'),
            "plugin_status": "loaded"
        }
```

**Tests to implement**: `tests/unit_tests/test_external_feature_eng.py`
- Plugin loading and configuration
- Feature generation delegation
- Plugin error handling

#### 2.2 PostprocessingPlugin (`app/postprocessing_plugin.py`)

**Dependencies**: ConfigurationManager
**Purpose**: Handle column decomposition and replacement

```python
class PostprocessingPlugin:
    """
    Handles postprocessing operations including column decomposition.
    Decomposes specified columns and replaces them with components.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration parameters."""
        self.params = config
        self._init_decomposers()
    
    def _init_decomposers(self) -> None:
        """Initialize decomposition methods."""
        self.decomposers = {}
        
        methods = self.params.get('decomposition_methods', [])
        decomp_params = self.params.get('decomposition_params', {})
        
        if 'STL' in methods:
            from .decomposers.stl_decomposer import STLDecomposer
            self.decomposers['STL'] = STLDecomposer(decomp_params)
        
        if 'Wavelet' in methods:
            from .decomposers.wavelet_decomposer import WaveletDecomposer
            self.decomposers['Wavelet'] = WaveletDecomposer(decomp_params)
        
        if 'MTM' in methods:
            from .decomposers.mtm_decomposer import MTMDecomposer
            self.decomposers['MTM'] = MTMDecomposer(decomp_params)
    
    def decompose_columns(self, data: pd.DataFrame) -> pd.DataFrame:
        """Decompose specified columns and replace with components."""
        if not self.params.get('use_postprocessing', False):
            return data
        
        result = data.copy()
        columns_to_decompose = self.params.get('decomposition_columns', [])
        
        for column in columns_to_decompose:
            if column not in result.columns:
                continue
            
            # Apply each decomposition method
            for method_name, decomposer in self.decomposers.items():
                components = decomposer.decompose(result[column])
                
                # Add components to result with systematic naming
                for comp_name, comp_values in components.items():
                    result[f"{column}_{comp_name}"] = comp_values
            
            # Remove original column
            result = result.drop(column, axis=1)
        
        return result
```

**Tests to implement**: `tests/unit_tests/test_postprocessing_plugin.py`
- STL decomposition behavior
- Wavelet decomposition configuration
- Multiple decomposition methods
- Systematic feature naming

#### 2.3 DataSplitter (`app/data_splitter.py`)

**Dependencies**: ConfigurationManager
**Purpose**: Split data into six datasets (d1-d6)

```python
class DataSplitter:
    """
    Splits data into six datasets for autoencoder and predictor training.
    Handles temporal ordering and overlap configuration.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration parameters."""
        self.params = config
    
    def split_data(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Split data into six datasets (d1-d6)."""
        auto_ratios = self.params['autoencoder_split_ratios']
        pred_ratios = self.params['predictor_split_ratios']
        overlap = self.params.get('split_overlap', 0.0)
        temporal = self.params.get('temporal_split', True)
        
        if temporal:
            return self._temporal_split(data, auto_ratios, pred_ratios, overlap)
        else:
            return self._random_split(data, auto_ratios, pred_ratios)
    
    def _temporal_split(self, data: pd.DataFrame, auto_ratios: List[float], 
                       pred_ratios: List[float], overlap: float) -> Dict[str, pd.DataFrame]:
        """Split data maintaining temporal order."""
        total_rows = len(data)
        
        # Calculate autoencoder split points
        auto_size = int(total_rows * (1 - overlap) / 2)  # Half for autoencoder path
        auto_d1_end = int(auto_size * auto_ratios[0])
        auto_d2_end = auto_d1_end + int(auto_size * auto_ratios[1])
        auto_d3_end = auto_d2_end + int(auto_size * auto_ratios[2])
        
        # Calculate predictor split points (with overlap)
        pred_start = int(total_rows * overlap)
        pred_size = total_rows - pred_start
        pred_d4_end = pred_start + int(pred_size * pred_ratios[0])
        pred_d5_end = pred_d4_end + int(pred_size * pred_ratios[1])
        
        return {
            'd1': data.iloc[0:auto_d1_end].copy(),
            'd2': data.iloc[auto_d1_end:auto_d2_end].copy(),
            'd3': data.iloc[auto_d2_end:auto_d3_end].copy(),
            'd4': data.iloc[pred_start:pred_d4_end].copy(),
            'd5': data.iloc[pred_d4_end:pred_d5_end].copy(),
            'd6': data.iloc[pred_d5_end:].copy()
        }
    
    def validate_no_leakage(self, splits: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Validate that there's no data leakage between splits."""
        validation_results = {
            'training_sets_clean': True,
            'train_val_test_clean': True,
            'training_overlaps': [],
            'forbidden_overlaps': []
        }
        
        # Check for overlaps between training sets (d1 and d4)
        if self.params.get('check_data_leakage', True):
            d1_indices = set(splits['d1'].index)
            d4_indices = set(splits['d4'].index)
            
            overlap = d1_indices.intersection(d4_indices)
            if overlap and self.params.get('split_overlap', 0.0) == 0.0:
                validation_results['training_sets_clean'] = False
                validation_results['training_overlaps'].append(('d1', 'd4', len(overlap)))
        
        return validation_results
```

**Tests to implement**: `tests/unit_tests/test_data_splitter.py`
- Six-dataset split generation
- Temporal ordering preservation
- Split validation and leakage detection

### Phase 3: Normalization Components (Level 3)

#### 3.1 AutoencoderNormalizer (`app/autoencoder_normalizer.py`)

**Dependencies**: ConfigurationManager, DataSplitter
**Purpose**: Z-score normalization for autoencoder path using d1 parameters

```python
class AutoencoderNormalizer:
    """
    Z-score normalizer for autoencoder datasets.
    Fits on d1, applies to d1, d2, d3.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration parameters."""
        self.params = config
        self.normalization_params = {}
        self.fitted = False
    
    def fit(self, d1_data: pd.DataFrame) -> None:
        """Fit normalizer on d1 dataset."""
        self.normalization_params = {}
        
        for column in d1_data.columns:
            if d1_data[column].dtype in ['object', 'datetime64[ns]']:
                continue  # Skip non-numeric columns
            
            mean_val = d1_data[column].mean()
            std_val = d1_data[column].std()
            
            # Handle zero standard deviation
            if std_val == 0 or np.isnan(std_val):
                std_val = 1.0
                logger.warning(f"Zero std for {column}, setting to 1.0")
            
            self.normalization_params[column] = {
                'mean': float(mean_val),
                'std': float(std_val)
            }
        
        self.fitted = True
        self._save_parameters()
    
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply z-score normalization using fitted parameters."""
        if not self.fitted:
            raise ValueError("Normalizer not fitted. Call fit() first.")
        
        result = data.copy()
        
        for column in result.columns:
            if column in self.normalization_params:
                params = self.normalization_params[column]
                result[column] = (result[column] - params['mean']) / params['std']
        
        return result
    
    def _save_parameters(self) -> None:
        """Save normalization parameters to JSON file."""
        filepath = self.params.get('autoencoder_norm_file', 'autoencoder_normalization.json')
        
        with open(filepath, 'w') as f:
            json.dump(self.normalization_params, f, indent=2)
        
        logger.info(f"Autoencoder normalization parameters saved to {filepath}")
    
    def get_parameters(self) -> Dict[str, Dict[str, float]]:
        """Get current normalization parameters."""
        return self.normalization_params.copy()
    
    def normalize_autoencoder_path(self, splits: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Normalize d1, d2, d3 using d1 parameters."""
        # Fit on d1
        self.fit(splits['d1'])
        
        # Transform all autoencoder datasets
        return {
            'd1': self.transform(splits['d1']),
            'd2': self.transform(splits['d2']),
            'd3': self.transform(splits['d3'])
        }
```

**Tests to implement**: `tests/unit_tests/test_autoencoder_normalizer.py`
- Z-score normalization behavior
- Parameter persistence in JSON format
- Zero standard deviation handling

#### 3.2 PredictorNormalizer (`app/predictor_normalizer.py`)

**Dependencies**: ConfigurationManager, DataSplitter
**Purpose**: Independent z-score normalization for predictor path using d4 parameters

```python
class PredictorNormalizer:
    """
    Z-score normalizer for predictor datasets.
    Fits on d4, applies to d4, d5, d6.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration parameters."""
        self.params = config
        self.normalization_params = {}
        self.fitted = False
    
    def fit(self, d4_data: pd.DataFrame) -> None:
        """Fit normalizer on d4 dataset."""
        self.normalization_params = {}
        
        for column in d4_data.columns:
            if d4_data[column].dtype in ['object', 'datetime64[ns]']:
                continue  # Skip non-numeric columns
            
            mean_val = d4_data[column].mean()
            std_val = d4_data[column].std()
            
            # Handle zero standard deviation
            if std_val == 0 or np.isnan(std_val):
                std_val = 1.0
                logger.warning(f"Zero std for {column}, setting to 1.0")
            
            self.normalization_params[column] = {
                'mean': float(mean_val),
                'std': float(std_val)
            }
        
        self.fitted = True
        self._save_parameters()
    
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply z-score normalization using fitted parameters."""
        if not self.fitted:
            raise ValueError("Normalizer not fitted. Call fit() first.")
        
        result = data.copy()
        
        for column in result.columns:
            if column in self.normalization_params:
                params = self.normalization_params[column]
                result[column] = (result[column] - params['mean']) / params['std']
        
        return result
    
    def _save_parameters(self) -> None:
        """Save normalization parameters to JSON file."""
        filepath = self.params.get('predictor_norm_file', 'predictor_normalization.json')
        
        with open(filepath, 'w') as f:
            json.dump(self.normalization_params, f, indent=2)
        
        logger.info(f"Predictor normalization parameters saved to {filepath}")
    
    def get_parameters(self) -> Dict[str, Dict[str, float]]:
        """Get current normalization parameters."""
        return self.normalization_params.copy()
    
    def normalize_predictor_path(self, splits: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Normalize d4, d5, d6 using d4 parameters."""
        # Fit on d4
        self.fit(splits['d4'])
        
        # Transform all predictor datasets
        return {
            'd4': self.transform(splits['d4']),
            'd5': self.transform(splits['d5']),
            'd6': self.transform(splits['d6'])
        }
```

**Tests to implement**: `tests/unit_tests/test_predictor_normalizer.py`
- Independent normalization calculation
- Different normalization scales
- Consistent application across d4, d5, d6

### Phase 4: Validation and Main Plugin (Level 4)

#### 4.1 ValidationManager (`app/validation_manager.py`)

**Dependencies**: All normalization components
**Purpose**: Comprehensive validation and quality assurance

```python
class ValidationManager:
    """
    Manages validation and quality assurance for the preprocessing pipeline.
    Performs data quality checks, normalization validation, and leakage detection.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration parameters."""
        self.params = config
    
    def validate_complete_pipeline(self, splits: Dict[str, pd.DataFrame], 
                                 auto_normalized: Dict[str, pd.DataFrame],
                                 pred_normalized: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Perform comprehensive validation of the complete pipeline."""
        validation_results = {
            'overall_status': True,
            'data_quality': self._validate_data_quality(splits),
            'normalization': self._validate_normalization(auto_normalized, pred_normalized),
            'splits': self._validate_splits(splits),
            'leakage': self._validate_no_leakage(splits)
        }
        
        # Overall status is true only if all validations pass
        validation_results['overall_status'] = all([
            validation_results['data_quality']['valid'],
            validation_results['normalization']['valid'],
            validation_results['splits']['valid'],
            validation_results['leakage']['valid']
        ])
        
        return validation_results
    
    def _validate_data_quality(self, splits: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Validate data quality across all splits."""
        results = {'valid': True, 'issues': []}
        
        for split_name, split_data in splits.items():
            # Check for minimum sample size
            min_samples = self.params.get('min_samples_per_split', 100)
            if len(split_data) < min_samples:
                results['valid'] = False
                results['issues'].append(f"{split_name} has {len(split_data)} samples, minimum is {min_samples}")
            
            # Check for missing values
            missing_count = split_data.isnull().sum().sum()
            if missing_count > 0:
                results['issues'].append(f"{split_name} has {missing_count} missing values")
            
            # Check for infinite values
            inf_count = np.isinf(split_data.select_dtypes(include=[np.number])).sum().sum()
            if inf_count > 0:
                results['valid'] = False
                results['issues'].append(f"{split_name} has {inf_count} infinite values")
        
        return results
    
    def _validate_normalization(self, auto_normalized: Dict[str, pd.DataFrame],
                              pred_normalized: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Validate normalization quality."""
        results = {'valid': True, 'issues': []}
        
        # Validate autoencoder normalization
        if self.params.get('validate_normalization', True):
            for dataset_name, dataset in auto_normalized.items():
                for column in dataset.select_dtypes(include=[np.number]).columns:
                    mean_val = dataset[column].mean()
                    std_val = dataset[column].std()
                    
                    # For d1, mean should be ≈0, std should be ≈1
                    if dataset_name == 'd1':
                        if abs(mean_val) > 1e-10:
                            results['issues'].append(f"d1 {column} mean {mean_val} not close to 0")
                        if abs(std_val - 1.0) > 1e-10:
                            results['issues'].append(f"d1 {column} std {std_val} not close to 1")
        
        return results
```

#### 4.2 DataPreprocessorPlugin (`preprocessor_plugins/data_preprocessor.py`)

**Dependencies**: All components
**Purpose**: Main orchestrator plugin following prediction_provider architecture

```python
class DataPreprocessorPlugin:
    """
    Main data preprocessor plugin following prediction_provider architecture.
    Orchestrates the complete preprocessing pipeline with full replicability.
    """
    
    # Plugin default configuration
    DEFAULT_CONFIG = {
        # [Same as ConfigurationManager.DEFAULT_CONFIG]
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize with plugin-specific parameters (self.params)."""
        # Start with plugin-specific default parameters
        self.params = self.DEFAULT_CONFIG.copy()
        
        # Update with provided configuration (merged by main app)
        if config:
            self.params.update(config)
        
        # Initialize all components with final parameters
        self._initialize_components()
        
        # Log the final parameters for replicability
        logger.info("DataPreprocessorPlugin initialized with final parameters")
        logger.debug(f"Final params: {json.dumps(self.params, indent=2)}")
    
    def _initialize_components(self):
        """Initialize all components with final parameters."""
        self.config_manager = ConfigurationManager(self.params)
        self.external_feature_eng = ExternalFeatureEngManager(self.params)
        self.postprocessing = PostprocessingPlugin(self.params)
        self.data_splitter = DataSplitter(self.params)
        self.autoencoder_normalizer = AutoencoderNormalizer(self.params)
        self.predictor_normalizer = PredictorNormalizer(self.params)
        self.validation_manager = ValidationManager(self.params)
    
    def preprocess_data(self, input_data: pd.DataFrame) -> Dict[str, Any]:
        """Main preprocessing pipeline method."""
        try:
            logger.info("Starting data preprocessing pipeline")
            
            # Phase 1: External Feature Engineering
            feature_engineered_data = self.external_feature_eng.process_features(input_data)
            logger.info(f"Feature engineering complete: {feature_engineered_data.shape}")
            
            # Phase 2: Postprocessing (Column Decomposition)
            decomposed_data = self.postprocessing.decompose_columns(feature_engineered_data)
            logger.info(f"Postprocessing complete: {decomposed_data.shape}")
            
            # Phase 3: Data Splitting
            splits = self.data_splitter.split_data(decomposed_data)
            logger.info(f"Data splitting complete: {[k + ':' + str(len(v)) for k, v in splits.items()]}")
            
            # Phase 4: Autoencoder Normalization
            auto_normalized = self.autoencoder_normalizer.normalize_autoencoder_path(splits)
            logger.info("Autoencoder normalization complete")
            
            # Phase 5: Predictor Normalization
            pred_normalized = self.predictor_normalizer.normalize_predictor_path(splits)
            logger.info("Predictor normalization complete")
            
            # Phase 6: Validation
            validation_results = self.validation_manager.validate_complete_pipeline(
                splits, auto_normalized, pred_normalized
            )
            
            if not validation_results['overall_status']:
                logger.warning(f"Validation issues detected: {validation_results}")
            
            # Combine all normalized datasets
            all_datasets = {**auto_normalized, **pred_normalized}
            
            return {
                'datasets': all_datasets,
                'validation': validation_results,
                'metadata': self._generate_metadata(input_data, all_datasets)
            }
            
        except Exception as e:
            logger.error(f"Preprocessing pipeline failed: {e}")
            raise
    
    def get_config(self) -> Dict[str, Any]:
        """Get final plugin parameters for replicability."""
        return self.params.copy()
    
    def save_config(self, filepath: str) -> None:
        """Save final plugin parameters to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.params, f, indent=2)
        logger.info(f"Plugin parameters saved to {filepath}")
    
    @classmethod
    def from_config_file(cls, filepath: str) -> 'DataPreprocessorPlugin':
        """Create plugin instance from saved parameters file."""
        with open(filepath, 'r') as f:
            params = json.load(f)
        return cls(config=params)
    
    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            "name": "DataPreprocessorPlugin",
            "version": "1.0.0",
            "description": "Complete data preprocessing with feature engineering, splitting, and dual normalization",
            "parameters": self.params,
            "components": {
                "external_feature_eng": "ExternalFeatureEngManager",
                "postprocessing": "PostprocessingPlugin",
                "data_splitter": "DataSplitter",
                "autoencoder_normalizer": "AutoencoderNormalizer",
                "predictor_normalizer": "PredictorNormalizer",
                "validation_manager": "ValidationManager"
            }
        }
```

## Implementation Timeline

### Week 1: Foundation (Phase 1)
- [ ] Implement ConfigurationManager with full parameter validation
- [ ] Create comprehensive unit tests for configuration management
- [ ] Establish project structure and build system
- [ ] Set up logging and error handling framework

### Week 2: Processing Components (Phase 2)
- [ ] Implement ExternalFeatureEngManager with plugin loading
- [ ] Implement PostprocessingPlugin with decomposition methods
- [ ] Implement DataSplitter with temporal and validation logic
- [ ] Create unit tests for all processing components

### Week 3: Normalization (Phase 3)
- [ ] Implement AutoencoderNormalizer with z-score and JSON persistence
- [ ] Implement PredictorNormalizer with independent scaling
- [ ] Create comprehensive normalization tests
- [ ] Implement component integration tests

### Week 4: Integration and Validation (Phase 4)
- [ ] Implement ValidationManager with comprehensive checks
- [ ] Implement main DataPreprocessorPlugin orchestrator
- [ ] Create integration and system tests
- [ ] Performance testing and optimization

### Week 5: Testing and Documentation
- [ ] Complete E2E test scenarios
- [ ] Performance benchmarking
- [ ] API documentation and examples
- [ ] Production deployment preparation

## Quality Assurance

### Code Quality Standards
- **Test Coverage**: Minimum 95% line coverage, 100% behavioral coverage
- **Code Style**: Black formatting, pylint score > 9.0
- **Type Hints**: Full type annotation for all public methods
- **Documentation**: Comprehensive docstrings for all classes and methods

### Performance Targets
- **Processing Time**: < 5 minutes for 1M rows
- **Memory Usage**: < 8GB peak for standard datasets
- **Scalability**: Linear scaling up to 10M rows

### Reliability Standards
- **Error Handling**: Graceful degradation for all error conditions
- **Data Integrity**: Zero data corruption under any circumstances
- **Reproducibility**: 100% deterministic results for identical inputs

This implementation architecture provides a complete blueprint for building the Data Preprocessor Plugin following the same modern architecture and BDD methodology used for the prediction_provider feeder plugin.
