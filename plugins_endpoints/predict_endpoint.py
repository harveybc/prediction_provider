#!/usr/bin/env python3
"""
Predict Endpoint Plugin for Prediction Provider.

Handles prediction requests via POST and GET methods with database storage.
"""

from flask import request, jsonify, g
from datetime import datetime
import json
import traceback
import threading
from app.models import PendingPredictionRequest

class PredictEndpointPlugin:
    """Predict Endpoint Plugin."""
    
    plugin_params = {
        "endpoint_route": "/predict",
        "methods": ["GET", "POST"],
        "auth_required": True,
        "default_batch_size": 32,
        "default_num_batches": 1,
        "max_concurrent_predictions": 5
    }
    
    plugin_debug_vars = ["endpoint_route", "methods", "auth_required"]
    
    def __init__(self, config=None):
        self.params = self.plugin_params.copy()
        self.config = config or {}
        self.prediction_threads = {}
        
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
        Register the predict endpoint with the Flask application.
        
        Args:
            app (Flask): Flask application instance
        """
        route = self.params.get('endpoint_route', '/predict')
        methods = self.params.get('methods', ['GET', 'POST'])
        
        @app.route(route, methods=methods, endpoint='predict')
        def predict():
            if request.method == 'POST':
                return self._handle_prediction_request()
            elif request.method == 'GET':
                return self._handle_prediction_status()
        
        print(f"Predict endpoint registered at {route} with methods {methods}")
    
    def _handle_prediction_request(self):
        """
        Handle POST request to create a new prediction request.
        
        Expected JSON payload:
        {
            "model_path": "path/to/model.keras",
            "target_datetime": "2024-01-01T12:00:00Z",
            "batch_size": 32,
            "features": ["feature1", "feature2", ...]
        }
        """
        try:
            # Parse request data
            data = request.get_json()
            if not data:
                return jsonify({'error': 'JSON payload required'}), 400
            
            # Validate required fields
            required_fields = ['model_path', 'target_datetime']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            # Parse and validate target_datetime
            try:
                target_datetime = datetime.fromisoformat(data['target_datetime'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SSZ)'}), 400
            
            # Extract optional parameters
            batch_size = data.get('batch_size', self.params['default_batch_size'])
            features = data.get('features', [])
            
            # Create prediction request in database
            prediction_request = PendingPredictionRequest(
                model_path=data['model_path'],
                target_datetime=target_datetime,
                batch_size=batch_size,
                features=json.dumps(features) if features else None,
                status='pending'
            )
            
            g.db_session.add(prediction_request)
            g.db_session.commit()
            
            # Start prediction processing in background thread
            thread = threading.Thread(
                target=self._process_prediction,
                args=(prediction_request.id,),
                daemon=True
            )
            thread.start()
            self.prediction_threads[prediction_request.id] = thread
            
            return jsonify({
                'request_id': prediction_request.id,
                'status': 'pending',
                'message': 'Prediction request created successfully'
            }), 201
            
        except Exception as e:
            print(f"Error creating prediction request: {e}")
            traceback.print_exc()
            return jsonify({'error': 'Internal server error'}), 500
    
    def _handle_prediction_status(self):
        """
        Handle GET request to retrieve prediction status and results.
        
        Query parameters:
        - request_id: ID of the prediction request
        """
        try:
            request_id = request.args.get('request_id')
            if not request_id:
                return jsonify({'error': 'request_id parameter required'}), 400
            
            try:
                request_id = int(request_id)
            except ValueError:
                return jsonify({'error': 'Invalid request_id format'}), 400
            
            # Query prediction request from database
            prediction_request = g.db_session.query(PendingPredictionRequest).filter_by(id=request_id).first()
            
            if not prediction_request:
                return jsonify({'error': 'Prediction request not found'}), 404
            
            # Return prediction request data
            response_data = prediction_request.to_dict()
            
            # If completed, include parsed results
            if prediction_request.status == 'completed' and prediction_request.results:
                try:
                    response_data['results'] = json.loads(prediction_request.results)
                except json.JSONDecodeError:
                    response_data['results'] = prediction_request.results
            
            return jsonify(response_data), 200
            
        except Exception as e:
            print(f"Error retrieving prediction status: {e}")
            traceback.print_exc()
            return jsonify({'error': 'Internal server error'}), 500
    
    def _process_prediction(self, request_id):
        """
        Process prediction request in background thread.
        
        Args:
            request_id (int): ID of the prediction request
        """
        from app.models import create_database_engine, get_session_maker
        from app.plugin_loader import load_plugin
        
        # Create new database session for this thread
        engine = create_database_engine(self.config.get('database_url', 'sqlite:///prediction_provider.db'))
        session_maker = get_session_maker(engine)
        session = session_maker()
        
        try:
            # Get prediction request
            prediction_request = session.query(PendingPredictionRequest).filter_by(id=request_id).first()
            if not prediction_request:
                print(f"Prediction request {request_id} not found")
                return
            
            # Update status to processing
            prediction_request.status = 'processing'
            prediction_request.updated_at = datetime.utcnow()
            session.commit()
            
            print(f"Processing prediction request {request_id}")
            
            # Load predictor plugin
            predictor_class, _ = load_plugin('predictor.plugins', self.config.get('predictor_plugin', 'default_predictor'))
            predictor_plugin = predictor_class(self.config)
            predictor_plugin.set_params(**self.config)
            
            # Load feeder plugin
            feeder_class, _ = load_plugin('feeder.plugins', self.config.get('feeder_plugin', 'default_feeder'))
            feeder_plugin = feeder_class(self.config)
            feeder_plugin.set_params(**self.config)
            
            # Load the Keras model
            print(f"Loading model from {prediction_request.model_path}")
            success = predictor_plugin.load_model(prediction_request.model_path)
            if not success:
                raise ValueError(f"Failed to load model from {prediction_request.model_path}")
            
            # Get input features from request or use default
            features = []
            if prediction_request.features:
                features = json.loads(prediction_request.features)
            
            # Configure feeder with request parameters
            feeder_config = {
                'target_datetime': prediction_request.target_datetime,
                'batch_size': prediction_request.batch_size,
                'features': features
            }
            feeder_plugin.set_params(**feeder_config)
            
            # Fetch required data using feeder plugin
            print(f"Fetching data for datetime {prediction_request.target_datetime}")
            data_result = feeder_plugin.fetch_data_for_prediction(
                target_datetime=prediction_request.target_datetime
            )
            
            if not data_result or data_result.get('data') is None:
                raise ValueError("No data available for the specified datetime and parameters")
            
            prediction_data = data_result['data']
            print(f"Fetched data shape: {prediction_data.shape}")
            
            # Make predictions with uncertainty
            print("Making predictions with uncertainty estimation...")
            predictions, uncertainties = predictor_plugin.predict_with_uncertainty(prediction_data)
            
            # Format results
            results = {
                'predictions': predictions.tolist() if hasattr(predictions, 'tolist') else predictions,
                'uncertainties': uncertainties.tolist() if hasattr(uncertainties, 'tolist') else uncertainties,
                'target_datetime': prediction_request.target_datetime.isoformat(),
                'data_shape': list(prediction_data.shape) if hasattr(prediction_data, 'shape') else None,
                'model_path': prediction_request.model_path,
                'features': features,
                'metadata': data_result.get('metadata', {}),
                'prediction_timestamp': datetime.utcnow().isoformat()
            }
            
            # Update request with results
            prediction_request.status = 'completed'
            prediction_request.results = json.dumps(results)
            prediction_request.updated_at = datetime.utcnow()
            session.commit()
            
            print(f"Prediction request {request_id} completed successfully")
            
        except Exception as e:
            print(f"Error processing prediction request {request_id}: {e}")
            traceback.print_exc()
            
            # Update request with error
            try:
                prediction_request = session.query(PendingPredictionRequest).filter_by(id=request_id).first()
                if prediction_request:
                    prediction_request.status = 'failed'
                    prediction_request.error_message = str(e)
                    prediction_request.updated_at = datetime.utcnow()
                    session.commit()
            except Exception as commit_error:
                print(f"Error updating request status: {commit_error}")
        
        finally:
            session.close()
            # Remove thread from tracking
            if request_id in self.prediction_threads:
                del self.prediction_threads[request_id]

# For backward compatibility
Plugin = PredictEndpointPlugin
