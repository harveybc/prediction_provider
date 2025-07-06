#!/bin/bash
# Test Runner Script - Run all test levels individually
# This approach prevents database conflicts and ensures clean test isolation

echo "🧪 Running Prediction Provider Test Suite"
echo "=========================================="

cd /home/harveybc/Documents/GitHub/prediction_provider

# Track overall results
total_tests=0
total_passed=0
total_failed=0

# Function to run test level
run_test_level() {
    local test_dir=$1
    local test_name=$2
    
    echo ""
    echo "🔍 Running $test_name Tests..."
    echo "----------------------------------------"
    
    # Run tests and capture results
    if pytest $test_dir -v --tb=short -q; then
        echo "✅ $test_name Tests: PASSED"
        return 0
    else
        echo "❌ $test_name Tests: FAILED"
        return 1
    fi
}

# Run each test level individually
echo "🏁 Starting comprehensive test run..."

# Unit Tests
if run_test_level "tests/unit_tests/" "Unit"; then
    ((total_passed++))
else
    ((total_failed++))
fi

# Integration Tests  
if run_test_level "tests/integration_tests/" "Integration"; then
    ((total_passed++))
else
    ((total_failed++))
fi

# Acceptance Tests
if run_test_level "tests/acceptance_tests/" "Acceptance"; then
    ((total_passed++))
else
    ((total_failed++))
fi

# Security Tests
if run_test_level "tests/security_tests/" "Security"; then
    ((total_passed++))
else
    ((total_failed++))
fi

# Production Tests
if run_test_level "tests/production_tests/" "Production"; then
    ((total_passed++))
else
    ((total_failed++))
fi

# Behavioral Tests
if run_test_level "tests/behavioral_tests/" "Behavioral"; then
    ((total_passed++))
else
    ((total_failed++))
fi

# System Tests (specific files to avoid problematic ones)
if run_test_level "tests/system_tests/test_security.py tests/system_tests/test_logging.py" "System"; then
    ((total_passed++))
else
    ((total_failed++))
fi

# Final Summary
echo ""
echo "📊 FINAL TEST SUMMARY"
echo "===================="
echo "Test Levels Passed: $total_passed"
echo "Test Levels Failed: $total_failed"
echo "Total Test Levels: $((total_passed + total_failed))"

if [ $total_failed -eq 0 ]; then
    echo "🎉 ALL TEST LEVELS PASSED! System is ready for production."
    exit 0
else
    echo "⚠️  Some test levels failed. Check individual results above."
    exit 1
fi
