#!/usr/bin/env python3
"""
Fast Test Status Checker - Check all test levels quickly
"""
import subprocess
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def run_test_level(test_dir, test_name):
    """Run a test level and return result."""
    try:
        cmd = ["python", "-m", "pytest", test_dir, "-v", "--tb=short", "-q"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return test_name, result.returncode == 0, len(result.stdout.split('\n'))
    except subprocess.TimeoutExpired:
        return test_name, False, 0
    except Exception as e:
        return test_name, False, 0

def main():
    print("🧪 QUICK TEST STATUS CHECK")
    print("=" * 30)
    
    # Change to correct directory
    os.chdir("/home/harveybc/Documents/GitHub/prediction_provider")
    
    # Test levels to check
    test_levels = [
        ("tests/unit_tests/", "Unit"),
        ("tests/integration_tests/", "Integration"),
        ("tests/acceptance_tests/", "Acceptance"),
        ("tests/security_tests/", "Security"),
        ("tests/production_tests/", "Production"),
        ("tests/behavioral_tests/", "Behavioral"),
        ("tests/system_tests/", "System")
    ]
    
    print(f"Running {len(test_levels)} test levels in parallel...")
    print()
    
    passed = 0
    failed = 0
    
    # Run tests in parallel for speed
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_test = {
            executor.submit(run_test_level, test_dir, test_name): test_name 
            for test_dir, test_name in test_levels
        }
        
        for future in as_completed(future_to_test):
            test_name, success, line_count = future.result()
            if success:
                print(f"✅ {test_name} Tests: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} Tests: FAILED")
                failed += 1
    
    print()
    print("📊 SUMMARY")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {failed} test level(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
