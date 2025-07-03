#!/usr/bin/env python3
"""
Default Endpoints Plugin

Provides a Flask-based API for the prediction provider, exposing health checks,
system info, and prediction results.
"""

from flask import Flask, jsonify
import sqlite3

class DefaultEndpointsPlugin:
    """
    Plugin for creating and running the API endpoints.
    """

    plugin_params = {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": False,
        "db_path": "prediction_provider.db"
    }

    plugin_debug_vars = ["host", "port", "debug"]

    def __init__(self, config):
        """
        Initializes the endpoints plugin.
        """
        self.params = self.plugin_params.copy()
        self.params.update(config)
        self.app = Flask(__name__)
        self.pipeline_plugin = None

    def set_params(self, **kwargs):
        """
        Updates the endpoint parameters.
        """
        self.params.update(kwargs)

    def initialize(self, pipeline_plugin):
        """
        Initializes the Flask app and registers the routes.
        """
        self.pipeline_plugin = pipeline_plugin
        self._register_routes()

    def _register_routes(self):
        """
        Registers all the API routes.
        """

        @self.app.route("/health", methods=['GET'])
        def health():
            status = self.pipeline_plugin.get_system_status() if self.pipeline_plugin else {"status": "unavailable"}
            is_healthy = status.get('system_ready', False)
            return jsonify(status), 200 if is_healthy else 503

        @self.app.route("/info", methods=['GET'])
        def info():
            # This endpoint could be expanded to return debug info from all plugins
            return jsonify(self.pipeline_plugin.get_debug_info())

        @self.app.route("/predictions", methods=['GET'])
        def get_predictions():
            try:
                conn = sqlite3.connect(self.params["db_path"])
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM predictions ORDER BY prediction_timestamp DESC LIMIT 100")
                rows = cursor.fetchall()
                conn.close()
                
                preds = []
                for row in rows:
                    preds.append({
                        "id": row[0],
                        "prediction_timestamp": row[1],
                        "prediction": row[2],
                        "uncertainty": row[3],
                        "metadata": row[4]
                    })
                return jsonify(preds)
            except Exception as e:
                return jsonify({"error": f"Failed to retrieve predictions: {e}"}), 500

    def run(self):
        """
        Runs the Flask application.
        """
        host = self.params.get("host", "0.0.0.0")
        port = self.params.get("port", 5000)
        debug = self.params.get("debug", False)
        print(f"--- Starting Endpoints Server at http://{host}:{port} ---")
        self.app.run(host=host, port=port, debug=debug)
