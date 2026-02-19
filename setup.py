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
            'default_pipeline=plugins_pipeline.default_pipeline:DefaultPipelinePlugin'
        ],
        # Data feeder plugins - Obtienen y preparan datos de entrada
        'feeder.plugins': [
            'default_feeder=plugins_feeder.default_feeder:DefaultFeeder'
        ],
        # Predictor plugins - Cargan modelos y generan predicciones
        'predictor.plugins': [
            'default_predictor=plugins_predictor.default_predictor:DefaultPredictor',
            'noisy_ideal_predictor=plugins_predictor.noisy_ideal_predictor:NoisyIdealPredictor'
        ],
        # API endpoints plugins - Definen endpoints RESTful individuales
        'endpoints.plugins': [
            'default_endpoints=plugins_endpoints.default_endpoints:DefaultEndpointsPlugin',
            'predict_endpoint=plugins_endpoints.predict_endpoint:PredictEndpointPlugin',
            'health_endpoint=plugins_endpoints.health_endpoint:HealthEndpointPlugin',
            'info_endpoint=plugins_endpoints.info_endpoint:InfoEndpointPlugin',
            'metrics_endpoint=plugins_endpoints.metrics_endpoint:MetricsEndpointPlugin'
        ],
        # API core plugins - Gestionan configuración central del servidor Flask
        'core.plugins': [
            'default_core=plugins_core.default_core:DefaultCorePlugin'
        ]
    },
    install_requires=[
        'fastapi',
        'uvicorn[standard]',
        'python-multipart',
        'flask',
        'pandas',
        'numpy',
        'scikit-learn',
        'tensorflow',
        'onnxruntime',
        'requests',
        'pyjwt',
        'flask-cors',
        'sqlalchemy'
    ],
    author='Harvey Bastidas',
    author_email='your.email@example.com',
    description=(
        'A prediction provider system that supports dynamic loading of plugins for data feeding, '
        'prediction models, API endpoints, pipeline orchestration, and API core functionality.'
    )
)
