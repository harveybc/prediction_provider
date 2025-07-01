#!/usr/bin/env python3
"""
Default Core Plugin for Prediction Provider.

Handles Flask application initialization, authentication, CORS, and global middleware.
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
import jwt
from functools import wraps
from datetime import datetime, timedelta
import os

class DefaultCorePlugin:
    """Default Core Plugin for Flask application setup."""
    
    plugin_params = {
        "auth_type": "none",  # none, basic, jwt
        "jwt_secret": "prediction_provider_secret_key",
        "jwt_expiration_hours": 24,
        "allowed_origins": ["*"],
        "cors_enabled": True,
        "debug": False,
        "database_url": "sqlite:///prediction_provider.db"
    }
    
    plugin_debug_vars = ["auth_type", "cors_enabled", "debug", "database_url"]
    
    def __init__(self, config):
        self.params = self.plugin_params.copy()
        self.config = config
        self.app = None
        
    def set_params(self, **kwargs):
        """
        Actualiza los parámetros del core combinando los parámetros específicos con la configuración global.
        """
        for key, value in kwargs.items():
            self.params[key] = value
    
    def get_debug_info(self):
        """
        Devuelve información de debug de los parámetros relevantes del core.
        """
        return {var: self.params.get(var) for var in self.plugin_debug_vars}
    
    def add_debug_info(self, debug_info):
        """
        Agrega la información de debug al diccionario proporcionado.
        """
        debug_info.update(self.get_debug_info())
    
    def init_app(self, config):
        """
        Initialize Flask application with core configuration.
        
        Args:
            config (dict): Global configuration dictionary
            
        Returns:
            Flask: Configured Flask application instance
        """
        print("Initializing Flask application...")
        
        # Create Flask app
        self.app = Flask(__name__)
        
        # Update params with config
        self.set_params(**config)
        
        # Configure Flask app
        self.app.config['SECRET_KEY'] = self.params.get('jwt_secret', 'prediction_provider_secret_key')
        self.app.config['DEBUG'] = self.params.get('debug', False)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = self.params.get('database_url', 'sqlite:///prediction_provider.db')
        
        # Setup CORS if enabled
        if self.params.get('cors_enabled', True):
            allowed_origins = self.params.get('allowed_origins', ['*'])
            CORS(self.app, origins=allowed_origins)
            print(f"CORS enabled for origins: {allowed_origins}")
        
        # Setup authentication middleware
        self._setup_authentication()
        
        # Setup database connection handling
        self._setup_database()
        
        # Setup error handlers
        self._setup_error_handlers()
        
        print(f"Flask application initialized with auth_type: {self.params.get('auth_type', 'none')}")
        
        return self.app
    
    def _setup_authentication(self):
        """Setup authentication middleware based on auth_type."""
        auth_type = self.params.get('auth_type', 'none')
        
        if auth_type == 'jwt':
            @self.app.before_request
            def verify_jwt():
                # Skip authentication for preflight requests
                if request.method == 'OPTIONS':
                    return
                
                # Skip authentication for health endpoint
                if request.endpoint in ['health', 'info']:
                    return
                
                auth_header = request.headers.get('Authorization')
                if not auth_header:
                    return jsonify({'error': 'Authorization header required'}), 401
                
                try:
                    token = auth_header.split(' ')[1]  # Bearer <token>
                    payload = jwt.decode(
                        token, 
                        self.params['jwt_secret'], 
                        algorithms=['HS256']
                    )
                    g.user_id = payload.get('user_id')
                    g.username = payload.get('username')
                except (IndexError, jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
                    return jsonify({'error': 'Invalid or expired token'}), 401
        
        elif auth_type == 'basic':
            @self.app.before_request
            def verify_basic_auth():
                # Skip authentication for preflight requests
                if request.method == 'OPTIONS':
                    return
                
                # Skip authentication for health endpoint
                if request.endpoint in ['health', 'info']:
                    return
                
                auth = request.authorization
                if not auth or not self._check_basic_auth(auth.username, auth.password):
                    return jsonify({'error': 'Invalid credentials'}), 401
    
    def _check_basic_auth(self, username, password):
        """Check basic authentication credentials."""
        # Simple hardcoded check - in production, use proper user management
        valid_users = self.params.get('valid_users', {'admin': 'password'})
        return username in valid_users and valid_users[username] == password
    
    def _setup_database(self):
        """Setup database connection handling."""
        from app.models import create_database_engine, get_session_maker
        
        @self.app.before_request
        def setup_db_session():
            """Create database session for each request."""
            if not hasattr(g, 'db_engine'):
                g.db_engine = create_database_engine(self.params['database_url'])
                g.db_session_maker = get_session_maker(g.db_engine)
                g.db_session = g.db_session_maker()
        
        @self.app.teardown_appcontext
        def close_db_session(exception):
            """Close database session after each request."""
            db_session = getattr(g, 'db_session', None)
            if db_session is not None:
                db_session.close()
    
    def _setup_error_handlers(self):
        """Setup global error handlers."""
        
        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({'error': 'Endpoint not found'}), 404
        
        @self.app.errorhandler(405)
        def method_not_allowed(error):
            return jsonify({'error': 'Method not allowed'}), 405
        
        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({'error': 'Internal server error'}), 500
    
    def generate_jwt_token(self, user_id, username):
        """
        Generate JWT token for authentication.
        
        Args:
            user_id (int): User ID
            username (str): Username
            
        Returns:
            str: JWT token
        """
        expiration_hours = self.params.get('jwt_expiration_hours', 24)
        payload = {
            'user_id': user_id,
            'username': username,
            'exp': datetime.utcnow() + timedelta(hours=expiration_hours),
            'iat': datetime.utcnow()
        }
        
        token = jwt.encode(payload, self.params['jwt_secret'], algorithm='HS256')
        return token

# For backward compatibility
Plugin = DefaultCorePlugin
