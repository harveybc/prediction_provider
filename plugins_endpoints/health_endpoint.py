#!/usr/bin/env python3
"""
Health Endpoint Plugin

Provides health check endpoints for the Prediction Provider API.
This plugin registers endpoints for checking the health and status of the application.
"""

from flask import Blueprint, jsonify
from datetime import datetime
import sys
import platform

class HealthEndpointPlugin:
    """
    Endpoint plugin that provides health check functionality.
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "health_endpoint_enabled": True,
        "health_endpoint_path": "/health",
        "detailed_health_check": True
    }
    
    # Debug variables for monitoring
    plugin_debug_vars = ["health_endpoint_enabled", "health_endpoint_path"]
    
    def __init__(self, config=None):
        """
        Initialize the health endpoint plugin.
        
        Args:
            config (dict): Configuration parameters
        """
        self.params = self.plugin_params.copy()
        self.start_time = datetime.utcnow()
        
        if config:
            self.set_params(**config)
    
    def set_params(self, **kwargs):
        """
        Update plugin parameters with provided configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        for key, value in kwargs.items():
            self.params[key] = value
    
    def get_debug_info(self):
        """
        Get debug information for this plugin.
        
        Returns:
            dict: Debug information
        """
        return {var: self.params.get(var) for var in self.plugin_debug_vars}
    
    def add_debug_info(self, debug_info):
        """
        Add debug information to the provided dictionary.
        
        Args:
            debug_info (dict): Dictionary to add debug info to
        """
        debug_info.update(self.get_debug_info())
    
    def register(self, app):
        """
        Register the health endpoints with the Flask application.
        
        Args:
            app: Flask application instance
        """
        if not self.params.get("health_endpoint_enabled", True):
            return
        
        health_bp = Blueprint('health', __name__)
        
        @health_bp.route(self.params.get("health_endpoint_path", "/health"), methods=['GET'])
        def health_check():
            """
            Perform a basic health check.
            
            Returns:
                JSON response with health status
            """
            try:
                health_data = {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "service": "prediction_provider"
                }
                
                # Add detailed information if enabled
                if self.params.get("detailed_health_check", True):
                    health_data.update(self._get_detailed_health_info())
                
                return jsonify(health_data)
                
            except Exception as e:
                return jsonify({
                    "status": "unhealthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "service": "prediction_provider",
                    "error": str(e)
                }), 500
        
        @health_bp.route("/health/ready", methods=['GET'])
        def readiness_check():
            """
            Check if the service is ready to serve requests.
            
            Returns:
                JSON response with readiness status
            """
            try:
                # Check database connectivity
                db_healthy = self._check_database_health()
                
                # Check if all required components are loaded
                components_healthy = self._check_components_health()
                
                is_ready = db_healthy and components_healthy
                
                return jsonify({
                    "ready": is_ready,
                    "timestamp": datetime.utcnow().isoformat(),
                    "checks": {
                        "database": db_healthy,
                        "components": components_healthy
                    }
                }), 200 if is_ready else 503
                
            except Exception as e:
                return jsonify({
                    "ready": False,
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                }), 500
        
        @health_bp.route("/health/live", methods=['GET'])
        def liveness_check():
            """
            Check if the service is alive.
            
            Returns:
                JSON response with liveness status
            """
            return jsonify({
                "alive": True,
                "timestamp": datetime.utcnow().isoformat(),
                "uptime": str(datetime.utcnow() - self.start_time)
            })
        
        app.register_blueprint(health_bp)
    
    def _get_detailed_health_info(self):
        """
        Get detailed health information.
        
        Returns:
            dict: Detailed health information
        """
        return {
            "version": self._get_version_info(),
            "uptime": str(datetime.utcnow() - self.start_time),
            "python_version": sys.version,
            "platform": platform.platform(),
            "start_time": self.start_time.isoformat()
        }
    
    def _get_version_info(self):
        """
        Get version information.
        
        Returns:
            str: Version information
        """
        try:
            # Try to get version from package info or config
            return "1.0.0"  # Default version
        except Exception:
            return "unknown"
    
    def _check_database_health(self):
        """
        Check database connectivity and health.
        
        Returns:
            bool: True if database is healthy, False otherwise
        """
        try:
            from app.models import get_db_session
            
            session = get_db_session()
            # Try a simple query to test connectivity
            session.execute("SELECT 1")
            session.close()
            return True
            
        except Exception as e:
            print(f"Database health check failed: {e}")
            return False
    
    def _check_components_health(self):
        """
        Check if all required components are healthy.
        
        Returns:
            bool: True if all components are healthy, False otherwise
        """
        try:
            # Add checks for critical components here
            # For now, just return True
            return True
            
        except Exception as e:
            print(f"Components health check failed: {e}")
            return False
