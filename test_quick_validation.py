#!/usr/bin/env python3
"""
Quick validation test to ensure STL integration is working properly.
"""

import sys
import traceback

def test_basic_imports():
    """Test basic imports."""
    try:
        import pandas as pd
        print("✅ Pandas import successful")
        
        import numpy as np
        print("✅ Numpy import successful")
        
        from plugins_feeder.real_feeder import RealFeederPlugin
        print("✅ Real feeder import successful")
        
        from plugins_feeder.stl_feature_generator import STLFeatureGenerator
        print("✅ STL feature generator import successful")
        
        from plugins_feeder.technical_indicators import technical_indicators
        print("✅ Technical indicators import successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False

def test_basic_functionality():
    """Test basic functionality."""
    try:
        import pandas as pd
        import numpy as np
        
        # Create sample data
        data = pd.DataFrame({
            'CLOSE': np.random.rand(100) * 100 + 50,
            'VOLUME': np.random.rand(100) * 1000000,
            'test_feature': np.random.rand(100)
        })
        
        # Test STL feature generator
        from plugins_feeder.stl_feature_generator import STLFeatureGenerator
        stl_gen = STLFeatureGenerator()
        
        # Test with sample data
        result = stl_gen.generate_features(data)
        print(f"✅ STL features generated. Shape: {result.shape}")
        print(f"   Features: {list(result.columns)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Functionality test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all validation tests."""
    print("🧪 Quick Validation Test")
    print("=" * 30)
    
    success_count = 0
    total_tests = 2
    
    # Test imports
    print("\n📦 Testing Imports...")
    if test_basic_imports():
        success_count += 1
    
    # Test functionality
    print("\n⚙️ Testing Functionality...")
    if test_basic_functionality():
        success_count += 1
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 30)
    print(f"✅ Passed: {success_count}/{total_tests}")
    print(f"❌ Failed: {total_tests - success_count}/{total_tests}")
    
    if success_count == total_tests:
        print("🎉 All tests passed! STL integration is working.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
