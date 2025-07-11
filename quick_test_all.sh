#!/bin/bash
# Quick Test Runner - Run all test levels with clear results
echo "🧪 PREDICTION PROVIDER TEST SUITE"
echo "=================================="
echo ""

cd /home/harveybc/Documents/GitHub/prediction_provider

# Initialize counters
total_levels=0
passed_levels=0
failed_levels=0

# Function to run test level with clear output
run_test_level() {
    local test_dir="$1"
    local test_name="$2"
    
    echo "📋 $test_name Tests:"
    echo "   Running..."
    
    ((total_levels++))
    
    # Run tests and capture result
    if timeout 60 python -m pytest "$test_dir" -v --tb=short -q > /dev/null 2>&1; then
        echo "   ✅ PASSED"
        ((passed_levels++))
    else
        echo "   ❌ FAILED"
        ((failed_levels++))
    fi
    echo ""
}

# Run all test levels
echo "🏁 Running all test levels..."
echo ""

run_test_level "tests/unit_tests/" "Unit"
run_test_level "tests/integration_tests/" "Integration" 
run_test_level "tests/acceptance_tests/" "Acceptance"
run_test_level "tests/security_tests/" "Security"
run_test_level "tests/production_tests/" "Production"
run_test_level "tests/behavioral_tests/" "Behavioral"
run_test_level "tests/system_tests/" "System"

# Summary
echo "📊 FINAL SUMMARY"
echo "================="
echo "Total Test Levels: $total_levels"
echo "Passed: $passed_levels"
echo "Failed: $failed_levels"
echo ""

if [ $failed_levels -eq 0 ]; then
    echo "🎉 ALL TEST LEVELS PASSED!"
    echo "✅ System is ready for production"
    exit 0
else
    echo "⚠️  $failed_levels test level(s) failed"
    echo "🔍 Run detailed tests to investigate:"
    echo "   ./run_all_tests.sh"
    exit 1
fi
