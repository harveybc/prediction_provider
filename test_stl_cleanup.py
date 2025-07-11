#!/usr/bin/env python3
"""
Quick test to verify STL integration is working after removing unused stl_preprocessor.py
"""

def test_imports():
    """Test that all necessary imports work."""
    try:
        from plugins_feeder.real_feeder import RealFeederPlugin
        from plugins_feeder.stl_feature_generator import STLFeatureGenerator
        from plugins_feeder.technical_indicators import TechnicalIndicatorCalculator
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_stl_functionality():
    """Test basic STL functionality."""
    try:
        from plugins_feeder.stl_feature_generator import STLFeatureGenerator
        import numpy as np
        import pandas as pd
        
        # Create test data
        data = pd.DataFrame({
            'CLOSE': np.random.randn(100) + 100
        })
        
        # Test STL feature generation
        stl_gen = STLFeatureGenerator()
        result = stl_gen.generate_stl_features(data)
        
        # Check if we get expected features
        expected_stl_features = ['log_return', 'stl_trend', 'stl_seasonal', 'stl_resid']
        has_stl_features = all(feat in result.columns for feat in expected_stl_features)
        
        if has_stl_features:
            print(f"✅ STL feature generation working: {len(result.columns)} features generated")
            print(f"   Features: {list(result.columns)}")
            return True
        else:
            print(f"❌ STL features missing. Got: {list(result.columns)}")
            return False
            
    except Exception as e:
        print(f"❌ STL functionality test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Quick Test: STL Integration After Cleanup")
    print("=" * 50)
    
    # Test imports
    imports_ok = test_imports()
    
    # Test STL functionality
    stl_ok = test_stl_functionality()
    
    # Summary
    print("\n📊 Test Results:")
    print(f"   Imports: {'✅ PASS' if imports_ok else '❌ FAIL'}")
    print(f"   STL Functionality: {'✅ PASS' if stl_ok else '❌ FAIL'}")
    
    if imports_ok and stl_ok:
        print("\n🎉 All tests passed! STL integration is working properly.")
    else:
        print("\n⚠️  Some tests failed. Please check the implementation.")
