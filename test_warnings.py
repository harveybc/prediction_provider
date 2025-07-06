#!/usr/bin/env python3
"""
Quick test to check if warnings are eliminated
"""
import warnings
import sys
import os

# Set up path
sys.path.insert(0, os.path.abspath('.'))

# Capture warnings
warnings.simplefilter("always")
warning_list = []

def custom_warning_handler(message, category, filename, lineno, file=None, line=None):
    warning_list.append(f"{category.__name__}: {message}")

old_showwarning = warnings.showwarning
warnings.showwarning = custom_warning_handler

try:
    # Import our auth module
    from app.auth import get_password_hash, verify_password
    
    # Test password hashing
    test_password = "test123"
    hashed = get_password_hash(test_password)
    verified = verify_password(test_password, hashed)
    
    print(f"Password hashing test: {'PASS' if verified else 'FAIL'}")
    
    # Show any warnings
    if warning_list:
        print(f"\nWarnings found ({len(warning_list)}):")
        for warning in warning_list:
            print(f"  - {warning}")
    else:
        print("\nNo warnings found!")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    warnings.showwarning = old_showwarning
