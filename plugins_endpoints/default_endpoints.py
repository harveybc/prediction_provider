#!/usr/bin/env python3
"""
Default Endpoints Plugin

Provides a Flask-based API for the prediction provider, exposing health checks,
system info, and prediction results.
"""

from flask import Flask, jsonify
from app.models import create_database_engine, get_session, Prediction

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
        self.engine = None

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
        self.engine = create_database_engine(f"sqlite:///{self.params['db_path']}")
        self._register_routes()

    def _register_routes(self):
        """
        Registers all the API routes.
        """

        @self.app.route("/health", methods=['GET'])
        def health():
            if not self.pipeline_plugin:
                return jsonify({"status": "unavailable", "system_ready": False}), 503
            
            status = self.pipeline_plugin.get_system_status()
            is_healthy = status.get('system_ready', False)
            
            # The test requires a simple 200 OK to confirm the server is running.
            # The detailed status can be used for more specific checks.
            if is_healthy:
                return jsonify(status), 200
            else:
                # Return 200 but indicate not ready, so polling continues
                return jsonify(status), 200

        @self.app.route("/info", methods=['GET'])
        def info():
            # This endpoint could be expanded to return debug info from all plugins
            return jsonify(self.pipeline_plugin.get_debug_info())

        @self.app.route("/predict", methods=['POST'])
        def predict():
            prediction_id = self.pipeline_plugin.request_prediction()
            if prediction_id:
                return jsonify({"prediction_id": prediction_id, "status": "pending"}), 202
            return jsonify({"error": "Failed to request prediction"}), 500

        @self.app.route("/predictions/<int:prediction_id>", methods=['GET'])
        def get_prediction_by_id(prediction_id):
            session = get_session(self.engine)
            try:
                prediction = session.query(Prediction).filter_by(id=prediction_id).first()
                if not prediction:
                    return jsonify({"error": "Prediction not found"}), 404

                if prediction.status == 'completed':
                    return jsonify(prediction.to_dict())
                else:
                    return jsonify({"status": prediction.status})
            except Exception as e:
                return jsonify({"error": f"Failed to retrieve prediction: {e}"}), 500
            finally:
                session.close()

        @self.app.route("/predictions", methods=['GET'])
        def get_predictions():
            session = get_session(self.engine)
            try:
                predictions = session.query(Prediction).order_by(Prediction.id.desc()).limit(100).all()
                return jsonify([p.to_dict() for p in predictions])
            except Exception as e:
                return jsonify({"error": f"Failed to retrieve predictions: {e}"}), 500
            finally:
                session.close()

    def run(self):
        """
        Runs the Flask application.
        """
        host = self.params.get("host", "0.0.0.0")
        port = self.params.get("port", 5000)
        debug = self.params.get("debug", False)
        print(f"--- Starting Endpoints Server at http://{host}:{port} ---")
        self.app.run(host=host, port=port, debug=debug)
