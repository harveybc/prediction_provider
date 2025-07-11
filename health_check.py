#!/usr/bin/env python3
"""
System Health Check - Verify core functionality is working
"""

def check_imports():
    """Check that our core modules can be imported."""
    try:
        from plugins_feeder.real_feeder import RealFeederPlugin
        from plugins_feeder.stl_feature_generator import STLFeatureGenerator
        from plugins_feeder.technical_indicators import TechnicalIndicatorCalculator
        return True, "All core imports successful"
    except Exception as e:
        return False, f"Import error: {e}"

def check_stl_functionality():
    """Check basic STL functionality."""
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
        expected_features = ['log_return', 'stl_trend', 'stl_seasonal', 'stl_resid']
        has_features = all(feat in result.columns for feat in expected_features)
        
        if has_features:
            return True, f"STL working: {len(result.columns)} features"
        else:
            return False, f"Missing STL features. Got: {list(result.columns)}"
            
    except Exception as e:
        return False, f"STL functionality error: {e}"

def check_syntax():
    """Check for syntax errors in core files."""
    import py_compile
    import os
    
    core_files = [
        'plugins_feeder/real_feeder.py',
        'plugins_feeder/stl_feature_generator.py', 
        'plugins_feeder/technical_indicators.py'
    ]
    
    for file_path in core_files:
        if os.path.exists(file_path):
            try:
                py_compile.compile(file_path, doraise=True)
            except py_compile.PyCompileError as e:
                return False, f"Syntax error in {file_path}: {e}"
        else:
            return False, f"Missing file: {file_path}"
    
    return True, f"All {len(core_files)} core files compile successfully"

def run_simple_test():
    """Run a simple pytest to check if testing works."""
    import subprocess
    try:
        # Try to run just one simple test
        result = subprocess.run([
            'python', '-m', 'pytest', 'tests/unit_tests/', '--collect-only', '-q'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            test_count = len([l for l in lines if 'test_' in l])
            return True, f"Test collection works: {test_count} tests found"
        else:
            return False, f"Test collection failed: {result.stderr}"
    except Exception as e:
        return False, f"Test framework error: {e}"

def main():
    print("🔍 SYSTEM HEALTH CHECK")
    print("=" * 25)
    
    checks = [
        ("Imports", check_imports),
        ("Syntax", check_syntax),
        ("STL Functionality", check_stl_functionality),
        ("Test Framework", run_simple_test)
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        try:
            success, message = check_func()
            if success:
                print(f"✅ {name}: {message}")
                passed += 1
            else:
                print(f"❌ {name}: {message}")
        except Exception as e:
            print(f"❌ {name}: Unexpected error: {e}")
    
    print()
    print(f"📊 Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 System is healthy!")
        print("💡 You can now run full tests with: ./run_all_tests.sh")
    else:
        print("⚠️  Some issues detected. Please check the errors above.")

if __name__ == "__main__":
    main()
