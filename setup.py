from setuptools import setup, find_packages

setup(
    name='prediction_provider',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'prediction_provider=app.main:main'
        ],
        # Pipeline plugins - Orquestan el flujo de procesamiento completo
        'pipeline.plugins': [
            'default_pipeline=pipeline_plugins.default_pipeline:Plugin'
        ],
        # Data feeder plugins - Obtienen y preparan datos de entrada
        'data_feeder.plugins': [
            'default_data_feeder=data_feeder_plugins.default_data_feeder:Plugin',
            'file_data_feeder=data_feeder_plugins.file_data_feeder:Plugin',
            'api_data_feeder=data_feeder_plugins.api_data_feeder:Plugin'
        ],
        # Predictor plugins - Cargan modelos y generan predicciones
        'predictor.plugins': [
            'default_predictor=predictor_plugins.default_predictor:Plugin',
            'keras_predictor=predictor_plugins.keras_predictor:Plugin',
            'onnx_predictor=predictor_plugins.onnx_predictor:Plugin',
            'remote_predictor=predictor_plugins.remote_predictor:Plugin'
        ],
        # API endpoints plugins - Definen endpoints RESTful individuales
        'api_endpoints.plugins': [
            'predict_endpoint=api_endpoints_plugins.predict_endpoint:Plugin',
            'health_endpoint=api_endpoints_plugins.health_endpoint:Plugin',
            'info_endpoint=api_endpoints_plugins.info_endpoint:Plugin',
            'metrics_endpoint=api_endpoints_plugins.metrics_endpoint:Plugin'
        ],
        # API core plugins - Gestionan configuración central del servidor Flask
        'api_core.plugins': [
            'default_api_core=api_core_plugins.default_api_core:Plugin',
            'jwt_auth_core=api_core_plugins.jwt_auth_core:Plugin',
            'cors_enabled_core=api_core_plugins.cors_enabled_core:Plugin'
        ]
    },
    install_requires=[
        'flask',
        'pandas',
        'numpy',
        'scikit-learn',
        'tensorflow',
        'onnxruntime',
        'requests',
        'pyjwt',
        'flask-cors'
    ],
    author='Harvey Bastidas',
    author_email='your.email@example.com',
    description=(
        'A prediction provider system that supports dynamic loading of plugins for data feeding, '
        'prediction models, API endpoints, pipeline orchestration, and API core functionality.'
    )
)
