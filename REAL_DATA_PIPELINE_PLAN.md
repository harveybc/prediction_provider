# Real Data Pipeline Implementation & Testing Plan

## 🎯 Objective
Implement and test real feeder and predictor plugins that process live EURUSD data and generate the exact same technical indicators and inputs that the predictor model was trained on.

## 📋 Implementation Tasks

### 1. Real Feeder Plugin Implementation
- **Goal**: Create a feeder plugin that pulls live EURUSD HLOC data
- **Data Source**: Real-time EURUSD bid price data
- **Target**: First 1000 rows matching the DATE_TIME column from `examples/data/pphase_3/normalized_d4.csv`
- **Output**: Raw HLOC (High, Low, Open, Close) values

### 2. Real Predictor Plugin Implementation  
- **Goal**: Process raw HLOC data through the complete technical indicator pipeline
- **Processing Steps**:
  - Calculate all technical indicators used in model training
  - Apply the same normalization/preprocessing steps
  - Generate the exact input format expected by the predictor model
- **Output**: Processed data ready for model inference

### 3. Data Pipeline Validation Test
- **Test Name**: `test_real_data_pipeline_accuracy`
- **Comparison Target**: `examples/data/pphase_3/normalized_d4.csv`
- **Tolerance**: 1e-3 (0.001) for numerical comparisons
- **Validation Points**:
  - Raw HLOC data accuracy
  - Technical indicator calculations
  - Normalization/preprocessing consistency
  - Final model input format

## 🧪 Test Implementation Plan

### Test Structure
```python
def test_real_data_pipeline_accuracy():
    """
    Test that real feeder + predictor plugins generate data matching
    the training dataset within 1e-3 tolerance.
    """
    # 1. Load reference data
    reference_data = pd.read_csv('examples/data/pphase_3/normalized_d4.csv')
    reference_dates = reference_data['DATE_TIME'].head(1000)
    
    # 2. Fetch real EURUSD data for same dates
    real_feeder = RealFeederPlugin()
    raw_data = real_feeder.fetch_eurusd_data(
        start_date=reference_dates.iloc[0],
        end_date=reference_dates.iloc[-1],
        count=1000
    )
    
    # 3. Process through real predictor pipeline
    real_predictor = RealPredictorPlugin()
    processed_data = real_predictor.process_data(raw_data)
    
    # 4. Compare with reference data (1e-3 tolerance)
    for column in processed_data.columns:
        if column in reference_data.columns:
            assert_allclose(
                processed_data[column].values,
                reference_data[column].head(1000).values,
                rtol=1e-3,
                atol=1e-3,
                err_msg=f"Column {column} differs beyond tolerance"
            )
```

### Data Source Requirements
- **Currency Pair**: EURUSD
- **Data Type**: Bid prices (HLOC)
- **Time Range**: Matching DATE_TIME column from reference dataset
- **Count**: First 1000 rows
- **Frequency**: Same as training data (likely 1-minute or 5-minute bars)

### Technical Indicators to Implement
Based on the model training, implement the exact same:
- Moving averages (SMA, EMA)
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- ATR (Average True Range)
- Any other indicators used in the original model training

### Data Processing Pipeline
1. **Raw Data Fetching**: EURUSD HLOC from external API/feed
2. **Technical Indicators**: Calculate all indicators with same parameters
3. **Feature Engineering**: Apply same transformations as training
4. **Normalization**: Use same scaling/normalization methods
5. **Final Formatting**: Match exact input format for predictor model

## 📊 Success Criteria
- ✅ Raw HLOC data matches expected values (within market data tolerance)
- ✅ All technical indicators calculated correctly (1e-3 tolerance)
- ✅ Normalization/preprocessing produces consistent results
- ✅ Final model input format matches training data structure
- ✅ Pipeline processes 1000 rows without errors
- ✅ Performance is acceptable for real-time usage

## 🔧 Implementation Notes
- Use same library versions as model training
- Implement error handling for data feed issues
- Add logging for debugging data discrepancies
- Consider market hours and data availability
- Document any parameter differences found

## 📁 File Structure
```
feeder_plugins/
├── real_eurusd_feeder.py          # Real data feeder
predictor_plugins/
├── real_technical_predictor.py    # Real indicator processor
tests/
├── test_real_data_pipeline.py     # Pipeline validation test
examples/data/pphase_3/
├── normalized_d4.csv              # Reference dataset
```

## 🌟 Next Session Goals
1. Implement real EURUSD feeder plugin
2. Implement real technical indicator predictor plugin
3. Create comprehensive pipeline validation test
4. Run validation against reference dataset
5. Debug and fix any data discrepancies
6. Document the complete real data pipeline

This will ensure the prediction system works with real market data exactly as it was trained! 🚀
