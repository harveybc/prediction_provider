#!/usr/bin/env python3
"""
Sync Core Plugin

Extends the default core plugin with synchronous binary-prediction endpoints
for integration with external strategy engines (e.g. heuristic-strategy's
``plugin_api_predictions``).

Endpoints added:
    GET  /api/v1/model/info      – predictor metadata (window size, etc.)
    POST /api/v1/predict/entry   – entry signals (buy + sell) for a tick
    POST /api/v1/predict/exit    – exit signal for an open order

Usage:
    python -m app.main --core_plugin sync_core \\
                       --predictor_plugin binary_ideal_oracle \\
                       --csv_file data.csv

No existing plugin files are modified — this is a standalone addition.
"""

import os as _os
_QUIET = _os.environ.get('PREDICTION_PROVIDER_QUIET', '0') == '1'

from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel, Field

# Re-use the same FastAPI ``app`` instance from the default core so all
# existing endpoints remain available.
from plugins_core.default_core import app, DefaultCorePlugin


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

# --- Entry ---

class EntryPredictRequest(BaseModel):
    """Request for entry binary predictions (should I open a buy/sell?)."""
    datetime: str = Field(
        ...,
        description="Tick timestamp in DD.MM.YYYY HH:MM:SS.000 format.",
        json_schema_extra={"example": "22.03.2017 08:00:00.000"},
    )
    tp: float = Field(
        default=5.0,
        description="Take-profit distance in pips.",
        json_schema_extra={"example": 5.0},
    )
    sl: float = Field(
        default=10.0,
        description="Stop-loss distance in pips.",
        json_schema_extra={"example": 10.0},
    )
    # Trading costs from HS so oracle can compute exact cost buffer
    spread_pips: float = Field(
        default=0.0,
        description="Broker spread in pips (0 = use oracle default).",
        json_schema_extra={"example": 2.0},
    )
    commission_per_lot: float = Field(
        default=0.0,
        description="Commission per standard lot (100K units) in USD (0 = use oracle default).",
        json_schema_extra={"example": 7.0},
    )
    slippage_pips: float = Field(
        default=0.0,
        description="Expected slippage in pips (0 = use oracle default).",
        json_schema_extra={"example": 1.0},
    )


class EntryPredictResponse(BaseModel):
    """Binary entry signals for both buy and sell directions."""
    buy_entry_binary: int = Field(
        description="1 = buy TP predicted to be hit before buy SL this week, 0 = otherwise.",
        json_schema_extra={"example": 1},
    )
    sell_entry_binary: int = Field(
        description="1 = sell TP predicted to be hit before sell SL this week, 0 = otherwise.",
        json_schema_extra={"example": 0},
    )
    bars_remaining: int = Field(
        default=0,
        description="Number of bars until Friday close (weekly horizon). Fewer bars = higher confidence.",
        json_schema_extra={"example": 48},
    )
    buy_confidence: float = Field(
        default=1.0,
        description="Confidence of buy prediction (1.0 = fully confident, 0.0 = no confidence). "
                    "Oracle always returns 1.0; Bayesian models return 1 - k*std.",
        json_schema_extra={"example": 1.0},
    )
    sell_confidence: float = Field(
        default=1.0,
        description="Confidence of sell prediction. Same semantics as buy_confidence.",
        json_schema_extra={"example": 1.0},
    )


# --- Exit ---

class ExitPredictRequest(BaseModel):
    """Request for exit prediction (should I keep or close my open order?)."""
    datetime: str = Field(
        ...,
        description="Tick timestamp in DD.MM.YYYY HH:MM:SS.000 format.",
        json_schema_extra={"example": "22.03.2017 12:00:00.000"},
    )
    direction: str = Field(
        ...,
        description="Direction of the open order: 'buy' or 'sell'.",
        json_schema_extra={"example": "buy"},
    )
    tp_price: float = Field(
        ...,
        description="Absolute take-profit price level of the open order.",
        json_schema_extra={"example": 1.0815},
    )
    sl_price: float = Field(
        ...,
        description="Absolute stop-loss price level of the open order.",
        json_schema_extra={"example": 1.0790},
    )


class ExitPredictResponse(BaseModel):
    """Binary exit signal."""
    exit_binary: int = Field(
        description="1 = TP still expected (keep open), 0 = TP unlikely (close early).",
        json_schema_extra={"example": 1},
    )
    exit_confidence: float = Field(
        default=1.0,
        description="Confidence of exit prediction (1.0 = fully confident). "
                    "Oracle always returns 1.0; Bayesian models return 1 - k*std.",
        json_schema_extra={"example": 1.0},
    )


# --- Model info ---

class ModelInfoResponse(BaseModel):
    """Predictor metadata."""
    model_name: str = Field(json_schema_extra={"example": "binary_ideal_oracle"})
    window_size: int = Field(description="Number of past bars required as input.", json_schema_extra={"example": 0})
    supported_types: list = Field(json_schema_extra={"example": ["entry", "exit"]})
    entry_directions: list = Field(json_schema_extra={"example": ["buy", "sell"]})
    exit_directions: list = Field(json_schema_extra={"example": ["buy", "sell"]})
    prediction_scope: str = Field(json_schema_extra={"example": "weekly"})
    required_columns: list = Field(
        default=["OPEN", "HIGH", "LOW", "CLOSE"],
        description="OHLC columns the model requires in the data window.",
        json_schema_extra={"example": ["OPEN", "HIGH", "LOW", "CLOSE"]},
    )
    accepts_ohlc_window: bool = Field(
        default=False,
        description="Whether the predictor can process an OHLC window sent in the request.",
        json_schema_extra={"example": False},
    )


# ---------------------------------------------------------------------------
# Helper: parse DD.MM.YYYY HH:MM:SS.000 timestamps
# ---------------------------------------------------------------------------

def _parse_timestamp(ts_str: str):
    import pandas as pd
    try:
        return pd.Timestamp(datetime.strptime(ts_str, "%d.%m.%Y %H:%M:%S.%f"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp format: {ts_str}")


def _get_predictor():
    predictor = globals().get("_LOADED_PLUGINS", {}).get("predictor")
    if predictor is None:
        raise HTTPException(status_code=503, detail="Predictor plugin not available")
    return predictor


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/model/info",
    response_model=ModelInfoResponse,
    tags=["predictions"],
    summary="Predictor model metadata",
)
async def model_info():
    """Return metadata about the loaded predictor (window size, supported types, etc.)."""
    predictor = _get_predictor()
    if hasattr(predictor, "get_model_info"):
        return predictor.get_model_info()
    return {
        "model_name": type(predictor).__name__,
        "window_size": 0,
        "supported_types": ["entry"],
        "entry_directions": ["buy", "sell"],
        "exit_directions": [],
        "prediction_scope": "unknown",
        "required_columns": ["OPEN", "HIGH", "LOW", "CLOSE"],
        "accepts_ohlc_window": False,
    }


@app.post(
    "/api/v1/predict/entry",
    response_model=EntryPredictResponse,
    tags=["predictions"],
    summary="Entry binary prediction (buy + sell)",
    responses={
        200: {"description": "Binary entry signals for both directions."},
        400: {"description": "Invalid timestamp format."},
        500: {"description": "Predictor internal error."},
        503: {"description": "No predictor plugin loaded."},
    },
)
async def predict_entry(req: EntryPredictRequest):
    """
    Return binary entry predictions for **both** buy and sell directions.

    The predictor evaluates whether the TP would be hit before the SL for each
    direction, scanning future bars until Friday close (weekly scope).

    | buy_entry | sell_entry | Strategy action          |
    |:---------:|:----------:|--------------------------|
    |     1     |     0      | Open **buy** order       |
    |     0     |     1      | Open **sell** order      |
    |     1     |     1      | Both viable (pick one)   |
    |     0     |     0      | No action                |
    """
    predictor = _get_predictor()
    ts = _parse_timestamp(req.datetime)

    if hasattr(predictor, "predict_entry"):
        try:
            result = predictor.predict_entry(
                ts, tp_pips=req.tp, sl_pips=req.sl,
                spread_pips=req.spread_pips,
                commission_per_lot=req.commission_per_lot,
                slippage_pips=req.slippage_pips,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Entry prediction failed: {e}")
        return {
            "buy_entry_binary": int(result.get("buy_entry_binary", 0)),
            "sell_entry_binary": int(result.get("sell_entry_binary", 0)),
            "bars_remaining": int(result.get("bars_remaining", 0)),
            "buy_confidence": float(result.get("buy_confidence", 1.0)),
            "sell_confidence": float(result.get("sell_confidence", 1.0)),
        }

    raise HTTPException(status_code=501, detail="Predictor does not support predict_entry")


@app.post(
    "/api/v1/predict/exit",
    response_model=ExitPredictResponse,
    tags=["predictions"],
    summary="Exit binary prediction (early close check)",
    responses={
        200: {"description": "Binary exit signal for the open order."},
        400: {"description": "Invalid timestamp or direction."},
        500: {"description": "Predictor internal error."},
        503: {"description": "No predictor plugin loaded."},
    },
)
async def predict_exit(req: ExitPredictRequest):
    """
    Return a binary exit prediction for an **already-open** order.

    - ``exit_binary = 1`` → TP is still predicted to be hit → **keep open**
    - ``exit_binary = 0`` → TP unlikely / SL expected first → **close early**
    """
    predictor = _get_predictor()
    ts = _parse_timestamp(req.datetime)

    direction = req.direction.lower()
    if direction not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail=f"Invalid direction: {req.direction}. Use 'buy' or 'sell'.")

    if hasattr(predictor, "predict_exit"):
        try:
            result = predictor.predict_exit(
                ts, direction=direction,
                tp_price=req.tp_price, sl_price=req.sl_price,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Exit prediction failed: {e}")
        return {
            "exit_binary": int(result.get("exit_binary", 0)),
            "exit_confidence": float(result.get("exit_confidence", 1.0)),
        }

    raise HTTPException(status_code=501, detail="Predictor does not support predict_exit")


# ---------------------------------------------------------------------------
# Noise control & metrics endpoints
# ---------------------------------------------------------------------------

class SetNoiseRequest(BaseModel):
    """Request to update noise_std on the running predictor."""
    noise_std: float = Field(
        ..., description="Gaussian noise standard deviation (0.0 = perfect oracle).",
        json_schema_extra={"example": 0.3},
    )


class MetricsResponse(BaseModel):
    """Confusion-matrix metrics of noisy predictions vs true oracle."""
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    total_predictions: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    accuracy: float = 0.0
    noise_std: float = 0.0


@app.post(
    "/api/v1/predict/set_noise",
    tags=["noise"],
    summary="Set noise_std and reset metrics counters",
)
async def set_noise(req: SetNoiseRequest):
    """Update noise_std on the loaded predictor and reset F1 counters."""
    predictor = _get_predictor()
    predictor.set_params(noise_std=req.noise_std)
    if hasattr(predictor, "reset_metrics"):
        predictor.reset_metrics()
    return {"noise_std": req.noise_std, "status": "ok"}


@app.get(
    "/api/v1/predict/metrics",
    response_model=MetricsResponse,
    tags=["noise"],
    summary="Get F1 / precision / recall metrics",
)
async def get_metrics():
    """Return confusion-matrix metrics accumulated since last reset."""
    predictor = _get_predictor()
    if hasattr(predictor, "get_metrics"):
        return predictor.get_metrics()
    raise HTTPException(status_code=501, detail="Predictor does not support get_metrics")


# ---------------------------------------------------------------------------
# Core plugin class
# ---------------------------------------------------------------------------

class SyncCorePlugin(DefaultCorePlugin):
    """
    Core plugin that inherits all behaviour from ``DefaultCorePlugin`` and
    adds entry/exit/info endpoints via the module-level routes above.

    The only override is ``start()`` so that uvicorn points at *this* module
    (ensuring the new routes are registered).
    """

    plugin_params = {
        "host": "127.0.0.1",
        "port": 8000,
        "reload": False,
        "workers": 1,
    }

    plugin_debug_vars = ["host", "port", "reload", "workers"]

    def set_plugins(self, plugins):
        """Pass plugins to parent and also expose them at this module level."""
        super().set_plugins(plugins)
        globals()["_LOADED_PLUGINS"] = plugins

    def start(self):
        """Start the FastAPI application via uvicorn, pointing at this module."""
        import uvicorn

        host = self.plugin_params.get("host", "127.0.0.1")
        port = self.plugin_params.get("port", 8000)
        reload = self.plugin_params.get("reload", False)
        workers = self.plugin_params.get("workers", 1)

        if not _QUIET:
            print(f"Starting FastAPI server (sync_core) on {host}:{port}")
        uvicorn.run(
            "plugins_core.sync_core:app",
            host=host,
            port=port,
            reload=reload,
            workers=workers,
        )


# For backward compatibility with plugin loading convention
Plugin = SyncCorePlugin
