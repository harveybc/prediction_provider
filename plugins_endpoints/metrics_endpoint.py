#!/usr/bin/env python3
"""
Metrics Endpoint Plugin

Provides system metrics and statistics endpoints for the Prediction Provider API.
This plugin registers endpoints for retrieving system health metrics, performance statistics,
and other monitoring information.
"""

from flask import Blueprint, jsonify, request
import psutil
import time
from datetime import datetime

class MetricsEndpointPlugin:
    """
    Endpoint plugin that provides system metrics and statistics.
    """
    
    # Plugin parameters with default values
    plugin_params = {
        "metrics_endpoint_enabled": True,
        "metrics_endpoint_path": "/metrics",
        "include_system_metrics": True,
        "include_prediction_stats": True
    }
    
    # Debug variables for monitoring
    plugin_debug_vars = ["metrics_endpoint_enabled", "metrics_endpoint_path"]
    
    def __init__(self, config=None):
        """
        Initialize the metrics endpoint plugin.
        
        Args:
            config (dict): Configuration parameters
        """
        self.params = self.plugin_params.copy()
        self.start_time = time.time()
        
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
        Register the metrics endpoints with the Flask application.
        
        Args:
            app: Flask application instance
        """
        if not self.params.get("metrics_endpoint_enabled", True):
            return
        
        metrics_bp = Blueprint('metrics', __name__)
        
        @metrics_bp.route(self.params.get("metrics_endpoint_path", "/metrics"), methods=['GET'])
        def get_metrics():
            """
            Get system and application metrics.
            
            Returns:
                JSON response with metrics data
            """
            try:
                metrics = {}
                
                # System metrics
                if self.params.get("include_system_metrics", True):
                    metrics["system"] = self._get_system_metrics()
                
                # Application metrics
                metrics["application"] = self._get_application_metrics()
                
                # Prediction statistics
                if self.params.get("include_prediction_stats", True):
                    metrics["predictions"] = self._get_prediction_stats()
                
                return jsonify({
                    "status": "success",
                    "timestamp": datetime.utcnow().isoformat(),
                    "metrics": metrics
                })
                
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": f"Failed to retrieve metrics: {str(e)}"
                }), 500
        
        app.register_blueprint(metrics_bp)
    
    def _get_system_metrics(self):
        """
        Get system resource metrics.
        
        Returns:
            dict: System metrics
        """
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent,
                    "used": psutil.virtual_memory().used
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "used": psutil.disk_usage('/').used,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                },
                "network": {
                    "bytes_sent": psutil.net_io_counters().bytes_sent,
                    "bytes_recv": psutil.net_io_counters().bytes_recv,
                    "packets_sent": psutil.net_io_counters().packets_sent,
                    "packets_recv": psutil.net_io_counters().packets_recv
                }
            }
        except Exception as e:
            return {"error": f"Failed to get system metrics: {str(e)}"}
    
    def _get_application_metrics(self):
        """
        Get application-specific metrics.
        
        Returns:
            dict: Application metrics
        """
        uptime = time.time() - self.start_time
        
        return {
            "uptime_seconds": uptime,
            "uptime_formatted": self._format_uptime(uptime),
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "current_time": datetime.utcnow().isoformat()
        }
    
    def _get_prediction_stats(self):
        """
        Get prediction-related statistics from the database.
        
        Returns:
            dict: Prediction statistics
        """
        try:
            from app.models import get_db_session, PendingPredictionRequest
            
            session = get_db_session()
            
            # Get total requests
            total_requests = session.query(PendingPredictionRequest).count()
            
            # Get requests by status
            pending = session.query(PendingPredictionRequest).filter_by(status='pending').count()
            processing = session.query(PendingPredictionRequest).filter_by(status='processing').count()
            completed = session.query(PendingPredictionRequest).filter_by(status='completed').count()
            failed = session.query(PendingPredictionRequest).filter_by(status='failed').count()
            
            session.close()
            
            return {
                "total_requests": total_requests,
                "pending": pending,
                "processing": processing,
                "completed": completed,
                "failed": failed,
                "success_rate": (completed / total_requests * 100) if total_requests > 0 else 0
            }
            
        except Exception as e:
            return {"error": f"Failed to get prediction stats: {str(e)}"}
    
    def _format_uptime(self, seconds):
        """
        Format uptime in a human-readable format.
        
        Args:
            seconds (float): Uptime in seconds
            
        Returns:
            str: Formatted uptime
        """
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m {secs}s"
        elif hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
