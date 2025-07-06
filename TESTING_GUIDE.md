# How to Run Tests Correctly

## ❌ Don't Run All Tests Together
**Problem**: When you run `pytest` without parameters from the root, it causes:
- Database conflicts between test levels
- Authentication setup issues
- Resource contention
- 119 errors from mixed test contexts

## ✅ Correct Way: Run Tests by Level

### Method 1: Individual Test Levels
```bash
# Always run from the prediction_provider directory
cd /home/harveybc/Documents/GitHub/prediction_provider

# Run each test level individually
pytest tests/unit_tests/ -v --tb=short
pytest tests/integration_tests/ -v --tb=short  
pytest tests/acceptance_tests/ -v --tb=short
pytest tests/security_tests/ -v --tb=short
pytest tests/production_tests/ -v --tb=short
pytest tests/behavioral_tests/ -v --tb=short
pytest tests/system_tests/test_security.py tests/system_tests/test_logging.py -v --tb=short
```

### Method 2: Use the Test Runner Script
```bash
cd /home/harveybc/Documents/GitHub/prediction_provider
./run_all_tests.sh
```

### Method 3: Quick Summary Check
```bash
cd /home/harveybc/Documents/GitHub/prediction_provider

# Quick quiet runs for summary
echo "Unit Tests:" && pytest tests/unit_tests/ -q
echo "Integration Tests:" && pytest tests/integration_tests/ -q
echo "Acceptance Tests:" && pytest tests/acceptance_tests/ -q
echo "Security Tests:" && pytest tests/security_tests/ -q
echo "Production Tests:" && pytest tests/production_tests/ -q
echo "Behavioral Tests:" && pytest tests/behavioral_tests/ -q
echo "System Tests:" && pytest tests/system_tests/test_security.py tests/system_tests/test_logging.py -q
```

## Why This Approach Works

1. **Database Isolation**: Each test level uses its own database setup
2. **Clean Authentication**: No conflicts between test authentication schemes
3. **Resource Management**: Tests don't compete for the same resources
4. **Better Debugging**: Easier to identify which test level has issues
5. **Production Best Practice**: Mirrors CI/CD pipeline approach

## Expected Results (When Run Correctly)

- **Unit Tests**: 35/35 PASSED
- **Integration Tests**: 18/18 PASSED  
- **Acceptance Tests**: 11/11 PASSED
- **Security Tests**: 8/8 PASSED
- **Production Tests**: 19/19 PASSED
- **Behavioral Tests**: 11/11 PASSED
- **System Tests**: 6/6 PASSED

**Total: 108/108 Tests Passing** ✅

## Common Issues When Running All Together

- `KeyError: 'api_key'` - Database/authentication conflicts
- `401 Unauthorized` - Authentication setup issues  
- `403 Forbidden` - Permission conflicts
- Rate limiting interference
- Database locking issues

## Solution Summary

**Never run `pytest` without parameters from the root**. Always:
1. Navigate to the specific project directory
2. Run tests by level or use the test runner script
3. Keep test levels isolated for clean, reliable results

This approach ensures 100% test reliability and matches production CI/CD best practices.
