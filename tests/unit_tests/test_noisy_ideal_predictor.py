"""Tests for NoisyIdealPredictor plugin."""
import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from plugins_predictor.noisy_ideal_predictor import NoisyIdealPredictor


@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample hourly OHLC CSV."""
    n = 200  # 200 hours (~8 days)
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    rng = np.random.default_rng(0)
    close = 1.1000 + np.cumsum(rng.normal(0, 0.0005, n))
    df = pd.DataFrame({
        "DATE_TIME": dates,
        "OPEN": close - rng.uniform(0, 0.0002, n),
        "HIGH": close + rng.uniform(0, 0.0005, n),
        "LOW": close - rng.uniform(0, 0.0005, n),
        "CLOSE": close,
    })
    path = tmp_path / "test_ohlc.csv"
    df.to_csv(path, index=False)
    return str(path)


class TestNoisyIdealPredictor:
    def test_init_defaults(self):
        p = NoisyIdealPredictor()
        assert p.params["noise_std"] == 0.0
        assert p.params["noise_seed"] == 42
        assert not p.data_loaded

    def test_load_data(self, sample_csv):
        p = NoisyIdealPredictor({"csv_file": sample_csv})
        assert p.data_loaded
        assert len(p._data) == 200

    def test_load_missing_file(self):
        with pytest.raises(FileNotFoundError):
            NoisyIdealPredictor({"csv_file": "/nonexistent/file.csv"})

    def test_predict_at_no_noise(self, sample_csv):
        p = NoisyIdealPredictor({"csv_file": sample_csv, "noise_std": 0.0})
        ts = p._data.index[10]
        result = p.predict_at(ts)
        assert len(result["hourly_predictions"]) == 6
        assert len(result["daily_predictions"]) == 6
        # With no noise, hourly prediction h=1 should equal actual close at index 11
        expected = float(p._data.iloc[11]["CLOSE"])
        assert result["hourly_predictions"][0] == pytest.approx(expected)

    def test_predict_at_with_noise(self, sample_csv):
        p = NoisyIdealPredictor({"csv_file": sample_csv, "noise_std": 0.001, "noise_seed": 123})
        ts = p._data.index[10]
        result = p.predict_at(ts)
        ideal = float(p._data.iloc[11]["CLOSE"])
        # Should NOT be exactly equal (noise added)
        assert result["hourly_predictions"][0] != pytest.approx(ideal, abs=1e-10)
        # But should be close (noise_std = 0.001)
        assert result["hourly_predictions"][0] == pytest.approx(ideal, abs=0.01)

    def test_reproducibility(self, sample_csv):
        """Same seed → same predictions."""
        p1 = NoisyIdealPredictor({"csv_file": sample_csv, "noise_std": 0.001, "noise_seed": 42})
        p2 = NoisyIdealPredictor({"csv_file": sample_csv, "noise_std": 0.001, "noise_seed": 42})
        r1 = p1.predict_at(p1._data.index[10])
        r2 = p2.predict_at(p2._data.index[10])
        np.testing.assert_array_almost_equal(r1["hourly_predictions"], r2["hourly_predictions"])
        np.testing.assert_array_almost_equal(r1["daily_predictions"], r2["daily_predictions"])

    def test_different_seeds(self, sample_csv):
        """Different seeds → different predictions."""
        p1 = NoisyIdealPredictor({"csv_file": sample_csv, "noise_std": 0.001, "noise_seed": 1})
        p2 = NoisyIdealPredictor({"csv_file": sample_csv, "noise_std": 0.001, "noise_seed": 2})
        r1 = p1.predict_at(p1._data.index[10])
        r2 = p2.predict_at(p2._data.index[10])
        assert r1["hourly_predictions"] != r2["hourly_predictions"]

    def test_generate_all_predictions(self, sample_csv):
        p = NoisyIdealPredictor({"csv_file": sample_csv, "noise_std": 0.0})
        result = p.generate_all_predictions()
        assert "hourly" in result
        assert "daily" in result
        assert result["hourly"].shape == (200, 6)
        assert result["daily"].shape == (200, 6)
        assert list(result["hourly"].columns) == [f"Prediction_h_{i}" for i in range(1, 7)]
        assert list(result["daily"].columns) == [f"Prediction_d_{i}" for i in range(1, 7)]

    def test_generate_all_no_noise_matches_ideal(self, sample_csv):
        """With zero noise, prediction h=1 at row i should equal close[i+1]."""
        p = NoisyIdealPredictor({"csv_file": sample_csv, "noise_std": 0.0})
        result = p.generate_all_predictions()
        closes = p._data["CLOSE"].values
        for i in range(190):  # avoid boundary
            assert result["hourly"].iloc[i]["Prediction_h_1"] == pytest.approx(closes[i + 1])

    def test_predict_api_compat(self, sample_csv):
        """Test the predict() method for prediction provider API compatibility."""
        p = NoisyIdealPredictor({"csv_file": sample_csv, "noise_std": 0.0})
        ts = p._data.index[10].isoformat()
        result = p.predict({"timestamp": ts})
        assert "prediction" in result
        assert "daily_prediction" in result
        assert result["model_name"] == "noisy_ideal_predictor"
        assert len(result["prediction"]) == 6

    def test_boundary_handling(self, sample_csv):
        """Predictions near end of data should fall back to current price."""
        p = NoisyIdealPredictor({"csv_file": sample_csv, "noise_std": 0.0})
        last_ts = p._data.index[-1]
        result = p.predict_at(last_ts)
        last_close = float(p._data.iloc[-1]["CLOSE"])
        # All horizons should fall back to current close
        for pred in result["hourly_predictions"]:
            assert pred == pytest.approx(last_close)
