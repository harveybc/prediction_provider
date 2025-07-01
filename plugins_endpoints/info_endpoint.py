#!/usr/bin/env python3
"""
Info Endpoint Plugin

Provides informational endpoints for the Prediction Provider API.
This plugin registers endpoints for retrieving application information, documentation, and API details.
"""

from flask import Blueprint, jsonify
from datetime import datetime
import platform
import sys

class InfoEndpointPlugin:
    """
    Endpoint plugin that provides application information.
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "info_endpoint_enabled": True,
        "info_endpoint_path": "/info",
        "include_system_info": True,
        "include_api_docs": True
    }
    
    # Debug variables for monitoring
    plugin_debug_vars = ["info_endpoint_enabled", "info_endpoint_path"]
    
    def __init__(self, config=None):
        """
        Initialize the info endpoint plugin.
        
        Args:
            config (dict): Configuration parameters
        """
        self.params = self.plugin_params.copy()
        
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
        Register the info endpoints with the Flask application.
        
        Args:
            app: Flask application instance
        """
        if not self.params.get("info_endpoint_enabled", True):
            return
        
        info_bp = Blueprint('info', __name__)
        
        @info_bp.route(self.params.get("info_endpoint_path", "/info"), methods=['GET'])
        def get_info():
            """
            Get application information.
            
            Returns:
                JSON response with application information
            """
            try:
                info_data = {
                    "service": "prediction_provider",
                    "description": "AI-powered prediction service with plugin-based architecture",
                    "version": "1.0.0",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Add system information if enabled
                if self.params.get("include_system_info", True):
                    info_data["system"] = self._get_system_info()
                
                # Add API documentation if enabled
                if self.params.get("include_api_docs", True):
                    info_data["api"] = self._get_api_info()
                
                return jsonify(info_data)
                
            except Exception as e:
                return jsonify({
                    "error": f"Failed to retrieve information: {str(e)}"
                }), 500
        
        @info_bp.route("/info/version", methods=['GET'])
        def get_version():
            """
            Get version information.
            
            Returns:
                JSON response with version details
            """
            return jsonify({
                "version": "1.0.0",
                "build_date": "2024-01-01",
                "git_commit": "unknown",
                "python_version": sys.version,
                "platform": platform.platform()
            })
        
        @info_bp.route("/info/api", methods=['GET'])
        def get_api_info():
            """
            Get API documentation and endpoint information.
            
            Returns:
                JSON response with API documentation
            """
            return jsonify(self._get_api_info())
        
        app.register_blueprint(info_bp)
    
    def _get_system_info(self):
        """
        Get system information.
        
        Returns:
            dict: System information
        """
        return {
            "platform": platform.platform(),
            "architecture": platform.architecture(),
            "python_version": sys.version,
            "python_implementation": platform.python_implementation(),
            "machine": platform.machine(),
            "processor": platform.processor()
        }
    
    def _get_api_info(self):
        """
        Get API documentation and endpoint information.
        
        Returns:
            dict: API information
        """
        return {
            "base_url": "/api/v1",
            "endpoints": {
                "prediction": {
                    "path": "/predict",
                    "methods": ["POST", "GET"],
                    "description": "Create and retrieve prediction requests",
                    "parameters": {
                        "POST": [
                            {
                                "name": "model_path",
                                "type": "string",
                                "required": True,
                                "description": "Path to the trained model file"
                            },
                            {
                                "name": "target_datetime",
                                "type": "string",
                                "required": True,
                                "description": "Target datetime for prediction (ISO format)"
                            },
                            {
                                "name": "batch_size",
                                "type": "integer",
                                "required": False,
                                "default": 32,
                                "description": "Number of data batches to fetch"
                            },
                            {
                                "name": "features",
                                "type": "array",
                                "required": False,
                                "description": "List of feature names to include"
                            }
                        ],
                        "GET": [
                            {
                                "name": "request_id",
                                "type": "string",
                                "required": True,
                                "description": "UUID of the prediction request"
                            }
                        ]
                    }
                },
                "health": {
                    "path": "/health",
                    "methods": ["GET"],
                    "description": "Check service health status"
                },
                "metrics": {
                    "path": "/metrics",
                    "methods": ["GET"],
                    "description": "Get system and application metrics"
                },
                "info": {
                    "path": "/info",
                    "methods": ["GET"],
                    "description": "Get application information and documentation"
                }
            },
            "response_formats": {
                "success": {
                    "status": "success",
                    "data": "object",
                    "timestamp": "ISO datetime"
                },
                "error": {
                    "status": "error",
                    "message": "string",
                    "timestamp": "ISO datetime"
                }
            },
            "status_codes": {
                "200": "Success",
                "201": "Created",
                "400": "Bad Request",
                "404": "Not Found",
                "500": "Internal Server Error",
                "503": "Service Unavailable"
            }
        }
