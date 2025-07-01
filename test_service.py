#!/usr/bin/env python3
"""
Simple test script to verify the prediction provider service can start.
"""

import sys
import os
import threading
import time
import requests

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_service_startup():
    """Test if the prediction provider service can start up."""
    
    # Import after path is set
    from app.main import main
    from app.config import DEFAULT_VALUES
    
    print("Testing Prediction Provider service startup...")
    
    # Mock sys.argv for testing
    original_argv = sys.argv
    try:
        # Set test arguments
        sys.argv = [
            'prediction_provider',
            '--debug',
            '--server-port', '5001',  # Use different port for testing
            '--load-config', 'examples/config/default_config.json'
        ]
        
        # Start the service in a separate thread
        service_thread = threading.Thread(target=main, daemon=True)
        service_thread.start()
        
        # Give the service time to start
        time.sleep(5)
        
        # Test health endpoint
        try:
            response = requests.get('http://localhost:5001/health', timeout=5)
            if response.status_code == 200:
                print("✅ Service started successfully!")
                print(f"Health check response: {response.json()}")
                return True
            else:
                print(f"❌ Health check failed with status: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to service: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Service startup failed: {e}")
        return False
    finally:
        sys.argv = original_argv

if __name__ == "__main__":
    success = test_service_startup()
    if success:
        print("\n🎉 Prediction Provider service is working correctly!")
    else:
        print("\n💥 Prediction Provider service test failed!")
        sys.exit(1)
