# Data Preprocessor Plugin - BDD Design Specification

## Executive Summary

This document defines the behavioral requirements and design for a modern Data Preprocessor Plugin that follows the same architecture and methodology as the prediction_provider repo. The plugin will handle feature engineering, decomposition, data splitting, and z-score normalization with complete replicability and isolation.

## Business Requirements

### Primary Objectives
1. **Modular Processing Pipeline**: Use external feature-eng and postprocessing plugins
2. **Six-Dataset Split**: Generate d1,d2,d3 (autoencoder) and d4,d5,d6 (predictor) datasets
3. **Dual Z-Score Normalization**: Separate normalization parameters for autoencoder and predictor paths
4. **Perfect Replicability**: All processing parameters explicit and configurable
5. **Modern Architecture**: Follow prediction_provider plugin structure and config merging

### Secondary Objectives
1. **Comprehensive Testing**: Full BDD test coverage at all levels
2. **Hierarchical Components**: Clear component relationships and dependencies
3. **Per-Feature Normalization**: Save mean/std per feature in separate JSON files
4. **Plugin Isolation**: Complete self-containment for use in any application

## Functional Requirements

### F1: External Feature Engineering Integration
**As a** data scientist
**I want** to use external feature-eng preprocessing plugins for technical indicators
**So that** I can leverage existing feature engineering capabilities

#### Acceptance Criteria:
- [ ] Plugin can load and configure external feature-eng plugins
- [ ] Technical indicators are calculated using external plugins
- [ ] Configuration is passed through to external plugins
- [ ] External plugin processing is isolated and reproducible

### F2: Column Decomposition and Replacement
**As a** data scientist  
**I want** to decompose configured columns and replace them with their decompositions
**So that** I can use advanced signal processing features

#### Acceptance Criteria:
- [ ] Postprocessing plugin decomposes specified columns
- [ ] Original columns are replaced by decomposition components
- [ ] Decomposition parameters are configurable
- [ ] Decomposition is applied before main preprocessing

### F3: Six-Dataset Split Generation
**As a** machine learning engineer
**I want** the preprocessor to split data into 6 specific datasets
**So that** I can train autoencoder and predictor models separately

#### Acceptance Criteria:
- [ ] d1: Autoencoder training dataset
- [ ] d2: Autoencoder validation dataset  
- [ ] d3: Autoencoder test dataset
- [ ] d4: Predictor training dataset
- [ ] d5: Predictor validation dataset
- [ ] d6: Predictor test dataset
- [ ] Split ratios are configurable
- [ ] Temporal ordering is preserved

### F4: Dual Z-Score Normalization
**As a** data scientist
**I want** separate z-score normalization for autoencoder and predictor paths
**So that** I can optimize each model's input distribution independently

#### Acceptance Criteria:
- [ ] d1 dataset used to fit autoencoder normalizer (calculate mean/std per feature)
- [ ] d4 dataset used to fit predictor normalizer (calculate mean/std per feature)
- [ ] d2,d3 normalized using d1 parameters
- [ ] d5,d6 normalized using d4 parameters
- [ ] d1 normalized using its own parameters
- [ ] d4 normalized using its own parameters

### F5: Per-Feature Normalization Parameters Storage
**As a** MLOps engineer
**I want** normalization parameters saved per feature in separate JSON files
**So that** I can reproduce exact normalization in production

#### Acceptance Criteria:
- [ ] autoencoder_normalization.json: {feature_name: {mean: X, std: Y}}
- [ ] predictor_normalization.json: {feature_name: {mean: X, std: Y}}
- [ ] Parameters saved after fitting on d1 and d4 respectively
- [ ] JSON files can be loaded for production inference
- [ ] Each feature has explicit mean and standard deviation

### F6: Modern Plugin Architecture
**As a** software engineer
**I want** the preprocessor to follow prediction_provider architecture
**So that** it integrates seamlessly with existing systems

#### Acceptance Criteria:
- [ ] Same folder structure as prediction_provider
- [ ] Plugin initialization with DEFAULT_CONFIG and self.params
- [ ] Config merging using app.config_merger
- [ ] Plugin loading using app.plugin_loader
- [ ] Hierarchical component structure
- [ ] Complete isolation and replicability

## Non-Functional Requirements

### NF1: Performance
- Process datasets up to 1M rows within 5 minutes
- Memory usage stays below 8GB for standard datasets
- Incremental processing capability for large datasets

### NF2: Reliability  
- 99.9% success rate for valid input data
- Graceful error handling with descriptive messages
- Automatic recovery from transient failures

### NF3: Maintainability
- 100% test coverage for behavioral requirements
- Clear separation of concerns between components
- Comprehensive logging at all processing stages

### NF4: Replicability
- Identical outputs for identical inputs and configuration
- All randomness controlled by configurable seeds
- Complete parameter traceability

## Component Architecture

### High-Level Components

```
DataPreprocessorPlugin
├── ExternalFeatureEngPlugin (external)
├── PostprocessingPlugin
├── DataSplitter
├── AutoencoderNormalizer
├── PredictorNormalizer
├── ConfigurationManager
└── ValidationManager
```

### Component Relationships

#### Level 1: Core Plugin
- `DataPreprocessorPlugin`: Main orchestrator with self.params

#### Level 2: Processing Components
- `ExternalFeatureEngPlugin`: Technical indicators and feature engineering
- `PostprocessingPlugin`: Column decomposition and replacement
- `DataSplitter`: Six-dataset split generation

#### Level 3: Normalization Components  
- `AutoencoderNormalizer`: Z-score normalization for d1,d2,d3 using d1 parameters
- `PredictorNormalizer`: Z-score normalization for d4,d5,d6 using d4 parameters

#### Level 4: Support Components
- `ConfigurationManager`: Parameter management and JSON I/O
- `ValidationManager`: Data quality and consistency validation

### Component Dependencies

```
DataPreprocessorPlugin
    depends_on: [ConfigurationManager]
    
ExternalFeatureEngPlugin
    depends_on: [ConfigurationManager]
    
PostprocessingPlugin  
    depends_on: [ExternalFeatureEngPlugin, ConfigurationManager]
    
DataSplitter
    depends_on: [PostprocessingPlugin, ConfigurationManager]
    
AutoencoderNormalizer
    depends_on: [DataSplitter, ConfigurationManager]
    
PredictorNormalizer
    depends_on: [DataSplitter, ConfigurationManager]
    
ValidationManager
    depends_on: [AutoencoderNormalizer, PredictorNormalizer]
```

## Data Flow Architecture

### Processing Pipeline
1. **Input Data** → Raw dataset with features
2. **External Feature Engineering** → Technical indicators added
3. **Postprocessing** → Column decomposition and replacement
4. **Data Splitting** → Six datasets (d1-d6) generated
5. **Autoencoder Normalization** → d1,d2,d3 z-score normalized using d1 stats
6. **Predictor Normalization** → d4,d5,d6 z-score normalized using d4 stats
7. **Validation** → Quality checks and parameter saving
8. **Output** → Six normalized datasets + two normalization JSON files

### Data Artifacts
- **Input**: Single unified dataset
- **Intermediate**: Feature-engineered dataset, decomposed dataset
- **Output**: Six normalized datasets (d1-d6)
- **Metadata**: autoencoder_normalization.json, predictor_normalization.json

## Configuration Specification

### Plugin Default Configuration

```python
DEFAULT_CONFIG = {
    # === External Feature Engineering ===
    "use_external_feature_eng": True,
    "feature_eng_plugin": "TechnicalIndicatorPlugin",
    "feature_eng_params": {
        "indicators": ["RSI", "MACD", "EMA", "Bollinger"],
        "timeframes": [1, 5, 15, 30],
    },
    
    # === Postprocessing Configuration ===
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
    
    # === Data Splitting Configuration ===
    "autoencoder_split_ratios": [0.7, 0.15, 0.15],  # d1, d2, d3
    "predictor_split_ratios": [0.7, 0.15, 0.15],    # d4, d5, d6
    "temporal_split": True,
    "split_overlap": 0.1,  # 10% overlap between autoencoder and predictor
    
    # === Normalization Configuration ===
    "normalization_method": "zscore",  # zscore or minmax
    "per_feature_normalization": True,
    "autoencoder_norm_file": "autoencoder_normalization.json",
    "predictor_norm_file": "predictor_normalization.json",
    "handle_outliers": True,
    "outlier_method": "iqr",  # iqr, zscore, or none
    
    # === Validation Configuration ===
    "validate_splits": True,
    "validate_normalization": True,
    "check_data_leakage": True,
    "min_samples_per_split": 100,
    
    # === Output Configuration ===
    "output_format": "csv",  # csv, parquet, hdf5
    "save_metadata": True,
    "output_precision": 6,
}
```

## Processing Flow Details

### Phase 1: Feature Engineering
1. Load external feature-eng plugin
2. Configure plugin with feature_eng_params
3. Calculate technical indicators
4. Validate feature additions

### Phase 2: Postprocessing  
1. Load postprocessing plugin
2. Decompose specified columns using configured methods
3. Replace original columns with decomposition components
4. Validate decomposition results

### Phase 3: Data Splitting
1. Determine split points based on ratios and temporal constraints
2. Create autoencoder datasets (d1, d2, d3)
3. Create predictor datasets (d4, d5, d6) with optional overlap
4. Validate split integrity and temporal ordering

### Phase 4: Autoencoder Normalization
1. Calculate mean and std for each feature in d1
2. Save parameters to autoencoder_normalization.json
3. Apply z-score normalization to d1, d2, d3 using d1 parameters
4. Validate normalization consistency

### Phase 5: Predictor Normalization  
1. Calculate mean and std for each feature in d4
2. Save parameters to predictor_normalization.json
3. Apply z-score normalization to d4, d5, d6 using d4 parameters
4. Validate normalization consistency

### Phase 6: Output and Validation
1. Save all six normalized datasets
2. Perform final validation checks
3. Generate processing metadata
4. Log completion statistics

## Error Handling Strategy

### Data Quality Errors
- **Missing Values**: Configurable handling (drop, impute, flag)
- **Invalid Ranges**: Outlier detection and handling
- **Inconsistent Types**: Automatic type conversion with validation

### Processing Errors
- **Plugin Failures**: Graceful degradation with alternative methods
- **Memory Issues**: Chunked processing for large datasets
- **I/O Errors**: Retry logic with exponential backoff

### Validation Errors
- **Split Validation**: Ensure no data leakage between splits
- **Normalization Validation**: Check for proper distribution
- **Feature Validation**: Verify feature consistency across datasets

## Success Metrics

### Functional Metrics
- [ ] All 6 datasets generated successfully
- [ ] Normalization parameters saved correctly for each feature
- [ ] External plugins integrated and functioning
- [ ] Perfect replicability achieved

### Quality Metrics
- [ ] 100% test coverage for behavioral requirements
- [ ] Zero data leakage between train/validation/test splits
- [ ] Consistent feature distributions within each path
- [ ] All components pass integration tests

### Performance Metrics
- [ ] Processing time under 5 minutes for 1M rows
- [ ] Memory usage under 8GB peak
- [ ] Successful processing of various dataset sizes

This design specification provides the foundation for implementing a robust, scalable, and maintainable data preprocessing plugin that meets all stated requirements while following best practices for software architecture and machine learning pipelines.
