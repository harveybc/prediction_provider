# Real Data Pipeline Test Template

## Test Overview
This test validates that the real data pipeline produces identical results to the training dataset within 1e-3 tolerance.

## Test Implementation Template

```python
import pandas as pd
import numpy as np
from numpy.testing import assert_allclose
import pytest
from datetime import datetime, timedelta

class TestRealDataPipeline:
    """
    Test suite for validating real data pipeline accuracy against training data.
    """
    
    def setup_method(self):
        """Load reference dataset for comparison."""
        self.reference_data = pd.read_csv('examples/data/pphase_3/normalized_d4.csv')
        self.reference_dates = self.reference_data['DATE_TIME'].head(1000)
        self.tolerance = 1e-3
    
    def test_real_data_pipeline_accuracy(self):
        """
        GIVEN: Reference dataset with known technical indicators
        WHEN: Real feeder fetches EURUSD data and predictor processes it
        THEN: Generated data matches reference within 1e-3 tolerance
        """
        # Arrange
        real_feeder = self._get_real_feeder()
        real_predictor = self._get_real_predictor()
        
        # Act: Fetch real data
        raw_data = real_feeder.fetch_eurusd_data(
            start_date=self.reference_dates.iloc[0],
            end_date=self.reference_dates.iloc[-1],
            count=1000
        )
        
        # Act: Process through predictor pipeline
        processed_data = real_predictor.process_data(raw_data)
        
        # Assert: Compare all columns
        self._assert_data_matches(processed_data)
    
    def test_hloc_data_accuracy(self):
        """
        GIVEN: Reference HLOC data
        WHEN: Real feeder fetches EURUSD data
        THEN: HLOC values match expected market data
        """
        # Test basic HLOC data fetching accuracy
        pass
    
    def test_technical_indicators_accuracy(self):
        """
        GIVEN: Reference technical indicators
        WHEN: Real predictor calculates indicators
        THEN: All indicators match reference within tolerance
        """
        # Test individual technical indicators
        pass
    
    def test_normalization_consistency(self):
        """
        GIVEN: Reference normalized data
        WHEN: Real predictor applies normalization
        THEN: Normalized values match reference exactly
        """
        # Test normalization/scaling consistency
        pass
    
    def test_model_input_format(self):
        """
        GIVEN: Reference model input format
        WHEN: Real predictor generates model input
        THEN: Input format matches exactly
        """
        # Test final model input format
        pass
    
    def _get_real_feeder(self):
        """Get real feeder plugin instance."""
        from feeder_plugins.real_eurusd_feeder import RealEURUSDFeeder
        return RealEURUSDFeeder()
    
    def _get_real_predictor(self):
        """Get real predictor plugin instance."""
        from predictor_plugins.real_technical_predictor import RealTechnicalPredictor
        return RealTechnicalPredictor()
    
    def _assert_data_matches(self, processed_data):
        """Assert processed data matches reference within tolerance."""
        for column in processed_data.columns:
            if column in self.reference_data.columns:
                reference_values = self.reference_data[column].head(1000).values
                processed_values = processed_data[column].values
                
                try:
                    assert_allclose(
                        processed_values,
                        reference_values,
                        rtol=self.tolerance,
                        atol=self.tolerance,
                        err_msg=f"Column {column} differs beyond tolerance {self.tolerance}"
                    )
                    print(f"✅ {column}: PASSED (within tolerance)")
                except AssertionError as e:
                    print(f"❌ {column}: FAILED - {e}")
                    raise
```

## Plugin Interface Templates

### Real Feeder Plugin Template
```python
class RealEURUSDFeeder:
    """Real EURUSD data feeder plugin."""
    
    def fetch_eurusd_data(self, start_date, end_date, count=1000):
        """
        Fetch real EURUSD HLOC data for specified date range.
        
        Args:
            start_date: Start date for data
            end_date: End date for data  
            count: Number of records to fetch
            
        Returns:
            DataFrame with HLOC data
        """
        # TODO: Implement real data fetching
        pass
```

### Real Predictor Plugin Template
```python
class RealTechnicalPredictor:
    """Real technical indicator predictor plugin."""
    
    def process_data(self, raw_data):
        """
        Process raw HLOC data through complete technical indicator pipeline.
        
        Args:
            raw_data: DataFrame with HLOC data
            
        Returns:
            DataFrame with processed technical indicators
        """
        # TODO: Implement technical indicator processing
        pass
```

## Test Data Analysis Template

```python
def analyze_reference_data():
    """Analyze reference dataset to understand required processing."""
    data = pd.read_csv('examples/data/pphase_3/normalized_d4.csv')
    
    print("📊 Reference Dataset Analysis")
    print("=" * 50)
    print(f"Shape: {data.shape}")
    print(f"Columns: {list(data.columns)}")
    print(f"Date range: {data['DATE_TIME'].min()} to {data['DATE_TIME'].max()}")
    print(f"Sample data:\n{data.head()}")
    
    # Identify technical indicators
    hloc_columns = ['HIGH', 'LOW', 'OPEN', 'CLOSE']
    indicator_columns = [col for col in data.columns if col not in hloc_columns + ['DATE_TIME']]
    
    print(f"\n📈 Technical Indicators Found:")
    for col in indicator_columns:
        print(f"  - {col}")
    
    return data

if __name__ == "__main__":
    analyze_reference_data()
```

## Next Session Checklist

- [ ] Analyze reference dataset structure
- [ ] Implement real EURUSD feeder plugin
- [ ] Implement real technical indicator predictor plugin
- [ ] Create comprehensive pipeline validation test
- [ ] Run validation against reference dataset
- [ ] Debug and fix any data discrepancies
- [ ] Document the complete real data pipeline

## Success Metrics
- 100% of technical indicators match within 1e-3 tolerance
- HLOC data accuracy verified against market data
- Pipeline processes 1000 rows without errors
- Real-time performance acceptable for production use

Sweet dreams! 🌙 Ready to build the real data pipeline when you return! 🚀
