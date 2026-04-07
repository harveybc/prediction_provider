#!/usr/bin/env python3
"""
Train binary entry and exit models from labeled datasets.

Usage:
    cd /home/harveybc/Documents/GitHub/prediction_provider
    python train_binary_models.py \\
        --train_file data/labeled/labeled_d1.csv \\
        --val_file   data/labeled/labeled_d2.csv \\
        --output_dir models/binary

Produces:
    models/binary/entry_model.keras          + _metadata.json + _scaler.pkl
    models/binary/exit_model.keras           + _metadata.json + _scaler.pkl
"""

import argparse
import json
import os
import numpy as np
import pandas as pd


def load_dataset(csv_path, datetime_col='DATE_TIME'):
    df = pd.read_csv(csv_path)
    if datetime_col in df.columns:
        df[datetime_col] = pd.to_datetime(df[datetime_col])
        df.set_index(datetime_col, inplace=True)
    df.sort_index(inplace=True)
    return df


def get_feature_columns(df):
    exclude = {'OPEN', 'HIGH', 'LOW', 'CLOSE',
               'buy_entry_label', 'sell_entry_label',
               'buy_exit_label', 'sell_exit_label',
               'bars_to_friday'}
    return [c for c in df.columns if c not in exclude]


def make_windows(df, feature_cols, label_cols, window_size):
    """Create sliding windows of features and their labels."""
    features = df[feature_cols].values.astype(np.float32)
    labels = df[label_cols].values.astype(np.float32)

    X, y = [], []
    for i in range(window_size, len(features)):
        X.append(features[i - window_size:i])
        y.append(labels[i])
    return np.array(X), np.array(y)


def build_entry_model(window_size, n_features, n_outputs=2):
    """Bidirectional LSTM → Dense for buy/sell entry classification."""
    import tensorflow as tf

    inputs = tf.keras.Input(shape=(window_size, n_features))
    x = tf.keras.layers.Bidirectional(
        tf.keras.layers.LSTM(64, return_sequences=True))(inputs)
    x = tf.keras.layers.Dropout(0.3)(x)
    x = tf.keras.layers.Bidirectional(
        tf.keras.layers.LSTM(32))(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    x = tf.keras.layers.Dense(32, activation='relu')(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    outputs = tf.keras.layers.Dense(n_outputs, activation='sigmoid')(x)

    model = tf.keras.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss='binary_crossentropy',
        metrics=['accuracy', tf.keras.metrics.AUC(name='auc')]
    )
    return model


def build_exit_model(window_size, n_features, n_outputs=1):
    """1D-CNN + LSTM for exit prediction (shorter horizon)."""
    import tensorflow as tf

    inputs = tf.keras.Input(shape=(window_size, n_features))
    x = tf.keras.layers.Conv1D(64, 3, activation='relu', padding='same')(inputs)
    x = tf.keras.layers.MaxPooling1D(2)(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    x = tf.keras.layers.LSTM(32)(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    x = tf.keras.layers.Dense(16, activation='relu')(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    outputs = tf.keras.layers.Dense(n_outputs, activation='sigmoid')(x)

    model = tf.keras.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss='binary_crossentropy',
        metrics=['accuracy', tf.keras.metrics.AUC(name='auc')]
    )
    return model


def main():
    parser = argparse.ArgumentParser(description="Train binary entry/exit models")
    parser.add_argument("--train_file", required=True, help="Labeled d1 CSV")
    parser.add_argument("--val_file", required=True, help="Labeled d2 CSV")
    parser.add_argument("--output_dir", default="models/binary")
    parser.add_argument("--entry_window", type=int, default=64)
    parser.add_argument("--exit_window", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--patience", type=int, default=10)

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    import tensorflow as tf
    from sklearn.preprocessing import StandardScaler
    import joblib

    # ── Load data ──
    print("Loading training data ...")
    train_df = load_dataset(args.train_file)
    val_df = load_dataset(args.val_file)
    feature_cols = get_feature_columns(train_df)
    print(f"  Features: {len(feature_cols)}")
    print(f"  Train rows: {len(train_df)}, Val rows: {len(val_df)}")

    # ── Fit scaler on training data ──
    scaler = StandardScaler()
    scaler.fit(train_df[feature_cols].values)

    train_df[feature_cols] = scaler.transform(train_df[feature_cols].values)
    val_df[feature_cols] = scaler.transform(val_df[feature_cols].values)

    # ===================================================================
    # ENTRY MODEL (buy/sell binary)
    # ===================================================================
    print("\n=== Training Entry Model ===")
    entry_labels = ['buy_entry_label', 'sell_entry_label']
    X_train_e, y_train_e = make_windows(train_df, feature_cols, entry_labels, args.entry_window)
    X_val_e, y_val_e = make_windows(val_df, feature_cols, entry_labels, args.entry_window)

    print(f"  Entry train: {X_train_e.shape}, val: {X_val_e.shape}")
    print(f"  Buy  label distribution (train): {y_train_e[:,0].mean():.3f}")
    print(f"  Sell label distribution (train): {y_train_e[:,1].mean():.3f}")

    entry_model = build_entry_model(args.entry_window, len(feature_cols), 2)
    entry_model.summary()

    entry_cb = [
        tf.keras.callbacks.EarlyStopping(
            monitor='val_auc', patience=args.patience, mode='max',
            restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6),
    ]

    entry_model.fit(
        X_train_e, y_train_e,
        validation_data=(X_val_e, y_val_e),
        epochs=args.epochs, batch_size=args.batch_size,
        callbacks=entry_cb, verbose=1
    )

    # Save entry model
    entry_path = os.path.join(args.output_dir, "entry_model.keras")
    entry_model.save(entry_path)
    print(f"  Saved entry model to {entry_path}")

    entry_meta = {
        "model_name": "binary_entry_predictor",
        "window_size": args.entry_window,
        "feature_columns": feature_cols,
        "label_columns": entry_labels,
        "n_features": len(feature_cols),
    }
    with open(entry_path.rsplit('.', 1)[0] + '_metadata.json', 'w') as f:
        json.dump(entry_meta, f, indent=2)

    scaler_path = entry_path.rsplit('.', 1)[0] + '_scaler.pkl'
    joblib.dump(scaler, scaler_path)
    print(f"  Saved scaler to {scaler_path}")

    # ===================================================================
    # EXIT MODEL (keep-open binary, uses buy_exit_label for buy direction)
    # ===================================================================
    print("\n=== Training Exit Model ===")
    # For exit, we train on buy_exit_label (buy direction); sell_exit_label (sell direction)
    # and add direction + tp/sl distance as extra features.
    # For simplicity, train a single exit model on interleaved buy/sell exit labels.

    exit_feature_cols = feature_cols.copy()
    # Add synthetic direction/tp/sl features for training
    # (In inference, these are provided by the strategy)
    train_exit = train_df.copy()
    val_exit = val_df.copy()

    # Create buy-direction exit samples
    buy_exit_train = train_exit.copy()
    buy_exit_train['direction_feat'] = 1.0
    buy_exit_train['tp_distance'] = 0.0  # normalized, filled below
    buy_exit_train['sl_distance'] = 0.0
    buy_exit_train['exit_label'] = buy_exit_train['buy_exit_label']

    sell_exit_train = train_exit.copy()
    sell_exit_train['direction_feat'] = -1.0
    sell_exit_train['tp_distance'] = 0.0
    sell_exit_train['sl_distance'] = 0.0
    sell_exit_train['exit_label'] = sell_exit_train['sell_exit_label']

    exit_train = pd.concat([buy_exit_train, sell_exit_train], axis=0)
    exit_train.sort_index(inplace=True)

    buy_exit_val = val_exit.copy()
    buy_exit_val['direction_feat'] = 1.0
    buy_exit_val['tp_distance'] = 0.0
    buy_exit_val['sl_distance'] = 0.0
    buy_exit_val['exit_label'] = buy_exit_val['buy_exit_label']

    sell_exit_val = val_exit.copy()
    sell_exit_val['direction_feat'] = -1.0
    sell_exit_val['tp_distance'] = 0.0
    sell_exit_val['sl_distance'] = 0.0
    sell_exit_val['exit_label'] = sell_exit_val['sell_exit_label']

    exit_val = pd.concat([buy_exit_val, sell_exit_val], axis=0)
    exit_val.sort_index(inplace=True)

    exit_feat_cols = exit_feature_cols + ['direction_feat', 'tp_distance', 'sl_distance']
    X_train_x, y_train_x = make_windows(exit_train, exit_feat_cols, ['exit_label'], args.exit_window)
    X_val_x, y_val_x = make_windows(exit_val, exit_feat_cols, ['exit_label'], args.exit_window)

    print(f"  Exit train: {X_train_x.shape}, val: {X_val_x.shape}")
    print(f"  Exit label distribution (train): {y_train_x.mean():.3f}")

    exit_model = build_exit_model(args.exit_window, len(exit_feat_cols), 1)
    exit_model.summary()

    exit_cb = [
        tf.keras.callbacks.EarlyStopping(
            monitor='val_auc', patience=args.patience, mode='max',
            restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6),
    ]

    exit_model.fit(
        X_train_x, y_train_x,
        validation_data=(X_val_x, y_val_x),
        epochs=args.epochs, batch_size=args.batch_size,
        callbacks=exit_cb, verbose=1
    )

    exit_path = os.path.join(args.output_dir, "exit_model.keras")
    exit_model.save(exit_path)
    print(f"  Saved exit model to {exit_path}")

    exit_meta = {
        "model_name": "binary_exit_predictor",
        "window_size": args.exit_window,
        "feature_columns": exit_feat_cols,
        "label_columns": ["exit_label"],
        "n_features": len(exit_feat_cols),
    }
    with open(exit_path.rsplit('.', 1)[0] + '_metadata.json', 'w') as f:
        json.dump(exit_meta, f, indent=2)

    exit_scaler_path = exit_path.rsplit('.', 1)[0] + '_scaler.pkl'
    joblib.dump(scaler, exit_scaler_path)

    print("\n=== Training Complete ===")
    print(f"Entry model: {entry_path}")
    print(f"Exit model:  {exit_path}")


if __name__ == "__main__":
    main()
