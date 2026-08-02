"""Deterministic mechanics policy emitting canonical, labeled AssetIntent.

``mechanics_only_not_alpha_claim``: every intent this policy emits is a
vehicle for measuring execution mechanics — fills, protection acceptance,
reconciliation — never an alpha claim (owner mandate 2026-08-02; doc 29 §7).

Determinism contract: identical (config, observation) input produces a
byte-identical canonical AssetIntent. Direction derives from the SHA-256 of
``cell_id:bar_time`` so the policy exercises both long and short mechanics
over time without any market opinion.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping

from trading_contracts import AssetIntent, content_hash


class MechanicsPolicyError(RuntimeError):
    """Fail-closed policy rejection."""


@dataclass(frozen=True)
class MechanicsPolicyConfig:
    """Resolved from JSON configuration; hashed into every emitted intent."""

    cell_id: str
    asset_id: str
    target_exposure_magnitude: float
    stop_fraction: float
    take_profit_fraction: float
    validity_hours: float
    policy_version: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MechanicsPolicyConfig":
        required = [
            "cell_id", "asset_id", "target_exposure_magnitude",
            "stop_fraction", "take_profit_fraction", "validity_hours",
            "policy_version",
        ]
        missing = [key for key in required if key not in value]
        if missing:
            raise MechanicsPolicyError(f"config missing keys: {missing}")
        magnitude = float(value["target_exposure_magnitude"])
        stop = float(value["stop_fraction"])
        take = float(value["take_profit_fraction"])
        if not (0.0 < magnitude <= 1.0):
            raise MechanicsPolicyError("target_exposure_magnitude in (0, 1]")
        if not (0.0 < stop < 1.0) or not (0.0 < take < 1.0):
            raise MechanicsPolicyError("stop/take fractions must be in (0, 1)")
        if float(value["validity_hours"]) <= 0:
            raise MechanicsPolicyError("validity_hours must be positive")
        return cls(
            cell_id=str(value["cell_id"]),
            asset_id=str(value["asset_id"]),
            target_exposure_magnitude=magnitude,
            stop_fraction=stop,
            take_profit_fraction=take,
            validity_hours=float(value["validity_hours"]),
            policy_version=str(value["policy_version"]),
        )


class MechanicsPolicy:
    """Pure ``decide(observation) -> AssetIntent``. No credentials, no
    submission authority, no network, no state."""

    PRODUCER_NAME = "prediction_provider.mechanics_policy"

    def __init__(self, config: MechanicsPolicyConfig) -> None:
        self.config = config
        self.config_hash = content_hash(
            {
                "cell_id": config.cell_id,
                "asset_id": config.asset_id,
                "target_exposure_magnitude": config.target_exposure_magnitude,
                "stop_fraction": config.stop_fraction,
                "take_profit_fraction": config.take_profit_fraction,
                "validity_hours": config.validity_hours,
                "policy_version": config.policy_version,
            }
        )

    def direction(self, bar_time: datetime) -> int:
        digest = hashlib.sha256(
            f"{self.config.cell_id}:{bar_time.isoformat()}".encode()
        ).hexdigest()
        return 1 if int(digest[-1], 16) % 2 == 0 else -1

    def decide(self, observation: Mapping[str, Any]) -> AssetIntent:
        """Emit one canonical labeled intent from a causal observation.

        Required observation keys: ``bar_time`` (timezone-aware datetime),
        ``reference_price`` (float > 0), ``quote_hash`` (provenance of the
        quote evidence). Missing or stale-shaped input fails closed.
        """
        bar_time = observation.get("bar_time")
        reference = observation.get("reference_price")
        quote_hash = observation.get("quote_hash")
        if not isinstance(bar_time, datetime) or bar_time.tzinfo is None:
            raise MechanicsPolicyError("bar_time must be timezone-aware")
        if not isinstance(reference, (int, float)) or isinstance(
            reference, bool
        ) or reference <= 0:
            raise MechanicsPolicyError("reference_price must be positive")
        if not quote_hash:
            raise MechanicsPolicyError("quote_hash provenance is required")

        side = self.direction(bar_time)
        if side > 0:
            stop = reference * (1.0 - self.config.stop_fraction)
            take = reference * (1.0 + self.config.take_profit_fraction)
        else:
            stop = reference * (1.0 + self.config.stop_fraction)
            take = reference * (1.0 - self.config.take_profit_fraction)

        input_hash = content_hash(
            {
                "bar_time": bar_time.isoformat(),
                "reference_price": reference,
                "quote_hash": quote_hash,
            }
        )
        return AssetIntent(
            object_id=f"mech-{self.config.cell_id}-{bar_time.isoformat()}",
            as_of=bar_time,
            valid_until=bar_time + timedelta(hours=self.config.validity_hours),
            producer={
                "name": self.PRODUCER_NAME,
                "version": self.config.policy_version,
            },
            trace_id=f"mech-{input_hash[-17:]}",
            config_hash=self.config_hash,
            cell_id=self.config.cell_id,
            asset_id=self.config.asset_id,
            action="target",
            target_exposure=side * self.config.target_exposure_magnitude,
            risk_geometry={
                "mode": "fixed_price",
                "stop_price": round(stop, 8),
                "take_profit_price": round(take, 8),
            },
            reason_codes=[
                "mechanics_only_not_alpha_claim",
                f"input:{input_hash}",
            ],
            artifact_hash=self.config_hash,
        )
