#!/usr/bin/env python3
"""
main.py

Punto de entrada de la aplicación Prediction Provider. Este script orquesta:
    - La carga y fusión de configuraciones (CLI, archivos locales y remotos).
    - La inicialización de los plugins: Pipeline, Feeder, Predictor, Endpoints y Core.
    - La selección entre ejecutar la optimización de hiperparámetros o ejecutar el servicio de predicción directamente.
    - El guardado de la configuración resultante de forma local y/o remota.
"""

import sys
import json
import pandas as pd
from typing import Any, Dict

from app.config_handler import (
    load_config,
    save_config,
    remote_load_config,
    remote_save_config,
    remote_log
)
from app.cli import parse_args
from app.config import DEFAULT_VALUES
from app.plugin_loader import load_plugin
from app.config_merger import merge_config, process_unknown_args

# Se asume que los siguientes plugins se cargan desde sus respectivos namespaces:
# - pipeline.plugins
# - feeder.plugins
# - predictor.plugins
# - endpoints.plugins
# - core.plugins

def main():
    """
    Orquesta la ejecución completa del sistema Prediction Provider, incluyendo la optimización (si se configura)
    y la ejecución del pipeline completo (data feeding, predicción, API endpoints y core functionality).
    """
    print("Parsing initial arguments...")
    args, unknown_args = parse_args()
    cli_args: Dict[str, Any] = vars(args)

    print("Loading default configuration...")
    config: Dict[str, Any] = DEFAULT_VALUES.copy()

    file_config: Dict[str, Any] = {}
    # Carga remota de configuración si se solicita
    if args.remote_load_config:
        try:
            file_config = remote_load_config(args.remote_load_config, args.username, args.password)
            print(f"Loaded remote config: {file_config}")
        except Exception as e:
            print(f"Failed to load remote configuration: {e}")
            sys.exit(1)

    # Carga local de configuración si se solicita
    if args.load_config:
        try:
            file_config = load_config(args.load_config)
            print(f"Loaded local config: {file_config}")
        except Exception as e:
            print(f"Failed to load local configuration: {e}")
            sys.exit(1)

    # Primera fusión de la configuración (sin parámetros específicos de plugins)
    print("Merging configuration with CLI arguments and unknown args (first pass, no plugin params)...")
    unknown_args_dict = process_unknown_args(unknown_args)
    config = merge_config(config, {}, {}, file_config, cli_args, unknown_args_dict)

    # Selección del plugins
    if not cli_args.get('pipeline_plugin'):
        cli_args['pipeline_plugin'] = config.get('pipeline_plugin', 'default_pipeline')
    plugin_name = config.get('pipeline_plugin', 'default_pipeline')
    
    
    # --- CARGA DE PLUGINS ---
    # Carga del Pipeline Plugin
    print(f"Loading Pipeline Plugin: {plugin_name}")
    try:
        pipeline_class, _ = load_plugin('pipeline.plugins', plugin_name)
        pipeline_plugin = pipeline_class(config)
        pipeline_plugin.set_params(**config)
    except Exception as e:
        print(f"Failed to load or initialize Pipeline Plugin '{plugin_name}': {e}")
        sys.exit(1)

    # Carga del Data Feeder Plugin
    # Selección del plugin si no se especifica
    plugin_name = config.get('feeder_plugin', 'default_feeder')
    print(f"Loading Plugin ..{plugin_name}")

    try:
        feeder_class, _ = load_plugin('feeder.plugins', plugin_name)
        feeder_plugin = feeder_class(config)
        feeder_plugin.set_params(**config)
    except Exception as e:
        print(f"Failed to load or initialize Feeder Plugin: {e}")
        sys.exit(1)

    # Carga del Predictor Plugin
    plugin_name = config.get('predictor_plugin', 'default_predictor')
    print(f"Loading Plugin ..{plugin_name}")
    try:
        predictor_class, _ = load_plugin('predictor.plugins', plugin_name)
        predictor_plugin = predictor_class(config)
        predictor_plugin.set_params(**config)
    except Exception as e:
        print(f"Failed to load or initialize Predictor Plugin: {e}")
        sys.exit(1)

    # Carga del API Endpoints Plugin(s) - Multiple plugins pueden ser cargados
    endpoint_plugins = []
    endpoint_plugin_names = config.get('endpoint_plugins', ['predict_endpoint'])  # Default to predict_endpoint
    
    for endpoint_plugin_name in endpoint_plugin_names:
        print(f"Loading Endpoint Plugin ..{endpoint_plugin_name}")
        try:
            endpoint_class, _ = load_plugin('endpoints.plugins', endpoint_plugin_name)
            endpoint_plugin = endpoint_class(config)
            endpoint_plugin.set_params(**config)
            endpoint_plugins.append(endpoint_plugin)
        except Exception as e:
            print(f"Failed to load or initialize Endpoint Plugin '{endpoint_plugin_name}': {e}")
            sys.exit(1)

    # Carga del API Core Plugin
    plugin_name = config.get('core_plugin', 'default_core')
    print(f"Loading Plugin ..{plugin_name}")
    try:
        core_class, _ = load_plugin('core.plugins', plugin_name)
        core_plugin = core_class(config)
        core_plugin.set_params(**config)
    except Exception as e:
        print(f"Failed to load or initialize Core Plugin: {e}")
        sys.exit(1)

    # fusión de configuración, integrando parámetros específicos de plugin pipeline
    print("Merging configuration with CLI arguments and unknown args (second pass, with plugin params)...")
    config = merge_config(config, pipeline_plugin.plugin_params, {}, file_config, cli_args, unknown_args_dict)
    # fusión de configuración, integrando parámetros específicos de plugin feeder
    config = merge_config(config, feeder_plugin.plugin_params, {}, file_config, cli_args, unknown_args_dict)
    # fusión de configuración, integrando parámetros específicos de plugin predictor
    config = merge_config(config, predictor_plugin.plugin_params, {}, file_config, cli_args, unknown_args_dict)
    # fusión de configuración, integrando parámetros específicos de plugins endpoints
    for endpoint_plugin in endpoint_plugins:
        config = merge_config(config, endpoint_plugin.plugin_params, {}, file_config, cli_args, unknown_args_dict)
    # fusión de configuración, integrando parámetros específicos de plugin core
    config = merge_config(config, core_plugin.plugin_params, {}, file_config, cli_args, unknown_args_dict)
    

    # --- DECISIÓN DE EJECUCIÓN ---
    # Iniciar el servidor Flask de Prediction Provider
    print("Starting Prediction Provider Flask server...")
    try:
        # El Core Plugin inicializa la aplicación Flask
        flask_app = core_plugin.init_app(config)
        
        # Los Endpoints Plugins registran todos sus endpoints en la aplicación Flask
        for endpoint_plugin in endpoint_plugins:
            endpoint_plugin.register(flask_app)
        
        # El Pipeline Plugin prepara el sistema de predicción
        pipeline_plugin.initialize_prediction_system(
            config,
            predictor_plugin,
            feeder_plugin
        )
        
        # Configurar el puerto del servidor
        server_port = config.get('server_port', 5000)
        server_host = config.get('server_host', '0.0.0.0')
        debug_mode = config.get('debug', False)
        
        print(f"Starting Flask server on {server_host}:{server_port}")
        print(f"Debug mode: {debug_mode}")
        
        # Iniciar el servidor Flask
        flask_app.run(
            host=server_host,
            port=server_port,
            debug=debug_mode,
            threaded=True
        )
        
    except Exception as e:
        print(f"Failed to start Prediction Provider server: {e}")
        sys.exit(1)
        
    # Guardado de la configuración local y remota
    if config.get('save_config'):
        try:
            save_config(config, config['save_config'])
            print(f"Configuration saved to {config['save_config']}.")
        except Exception as e:
            print(f"Failed to save configuration locally: {e}")

    if config.get('remote_save_config'):
        print(f"Remote saving configuration to {config['remote_save_config']}")
        try:
            remote_save_config(config, config['remote_save_config'], config.get('username'), config.get('password'))
            print("Remote configuration saved.")
        except Exception as e:
            print(f"Failed to save configuration remotely: {e}")

if __name__ == "__main__":
    main()
