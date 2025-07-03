# config.py

DEFAULT_VALUES = {
    # --- Server & Database Configuration ---
    # These parameters configure the Flask web server and the database connection.
    "server_host": "0.0.0.0",
    "server_port": 5000,
    "debug": False,
    "database_url": "sqlite:///predictions.db",

    # --- Plugin Configuration ---
    # Defines which plugins are loaded at runtime.
    "core_plugin": "default_core",
    "endpoint_plugins": ["predict_endpoint"],
    "pipeline_plugin": "default_pipeline",
    "feeder_plugin": "default_feeder",
    "predictor_plugin": "default_predictor",

    # --- Data Feeder Configuration ---
    # Parameters for the data feeder plugin, which handles data acquisition and preprocessing.
    "instrument": "EUR/USD",
    "n_batches": 1, # The number of batches to retrieve. Total records = n_batches * batch_size.
    "batch_size": 256, # The number of time steps (records) in each batch.
    "use_normalization_json": "examples/config/phase_2_normalizer_debug_out.json", # Path to the normalization config file.
    'target_column': 'CLOSE',

    # --- Predictor Configuration ---
    # Parameters for the predictor plugin, which handles model loading and inference.
    "model_path": "./predictor_model.keras", # Path to the trained Keras model.
    "window_size": 256,  # Number of time steps required by the model. Must match batch_size.
    "mc_samples": 100, # Number of Monte Carlo samples for uncertainty estimation.

    # --- Legacy & Training-Specific Parameters (Review for removal) ---
    # The following parameters are mostly related to model training, optimization, and evaluation.
    # They are not actively used by the prediction service in its default configuration.
    # 'plugin': 'ann',
    # 'load_config': None,
    # 'save_config': './config_out.json',
    # 'save_log': './debug_out.json',
    # 'quiet_mode': False,
    # 'force_date': False,
    # 'headers': True,
    # 'use_daily': False,
    # 'remote_log': None,
    # 'remote_load_config': None,
    # 'remote_save_config': None,
    # 'username': None,
    # 'password': None,
    # 'input_offset': 0,
    # "use_returns": True,
    # 'save_model': './predictor_model.keras',
    # 'load_model': None,
    # 'loss_plot_file': './loss_plot.png',
    # 'model_plot_file': './model_plot.png',
    # 'uncertainty_file': 'prediction_uncertainties.csv',
    # "target_scaling_factor": 1000,
    # "feature_extractor_file": None,
    # "train_fe" : False,
    # "x_train_file": "examples\\data\\phase_3\\phase_3_encoder_eval_d2.csv",
    # "y_train_file": "examples\\data\\phase_2\\exp_4\\normalized_d2.csv",
    # "x_validation_file": "examples\\data\\phase_3\\phase_3_encoder_eval_d3.csv",
    # "y_validation_file": "examples\\data\\phase_2\\exp_4\\normalized_d3.csv",
    # 'threshold_error': 0.000000001,
    # 'l2_reg': 1e-4,
    # 'early_patience': 30,
    # 'max_steps_train': 6300,
    # 'max_steps_val': 6300,
    # 'max_steps_test': 6300,
    # 'iterations': 3,
    # 'epochs': 1000,
    # 'use_sliding_window' : False,
    # "kl_weight": 1e-6,
    # "kl_anneal_epochs": 100,
    # "mmd_lambda": 0.1,
    # "overfitting_penalty": 0.1,
    # "min_delta": 1e-4,
    # "start_from_epoch": 10,
    # "penalty_close_lambda":0.0001,
    # "penalty_far_lambda":0.0001,
    # "plotted_horizon": 6,
    # "plot_color_predicted": "orange",
    # "plot_color_true": "blue",
    # "plot_color_uncertainty": "green",
    # "uncertainty_color_alpha": 0.01,
    # "plot_points": 240,
    # "use_strategy": False,
    # "strategy_plugin_group": "heuristic_strategy.plugins",
    # "strategy_plugin_name": "ls_pred_strategy",
    # "strategy_1h_prediction": "examples/results/phase_1/phase_1_cnn_25200_1h_prediction.csv",
    # "strategy_1h_uncertainty": "examples/results/phase_1/phase_1_cnn_25200_1h_uncertanties.csv",
    # "strategy_base_dataset": "examples/data/phase_1/phase_1_base_d3.csv",
    # "strategy_load_parameters": "examples/data/phase_1/strategy_parameters.json",
    # "optimizer_output_file": "optimizer_output.json"
}
