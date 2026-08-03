"""Provider-owned mechanics policy for the L0 demo-trading vertical.

Ruling R1 (2026-08-02): this module is importable and installed, is consumed
in-process by LTS during L0 and the bounded L1 mechanics canary, holds no
broker credentials and no submission authority, and its output is canonical
``AssetIntent`` carrying artifact/config/input hashes. The eventual provider
service endpoint must return byte-equivalent canonical output for identical
input (golden parity fixture in tests). Service integration is mandatory
before continuous L2.

Packaging note: this lives as a sub-project because the parent provider
distribution exposes a top-level package literally named ``app``, which
collides with the LTS ``app`` package in a shared environment. That landmine
is reported to the auditor; resolving it belongs to the pre-L2 service
integration.
"""
from .loader import ArtifactVerificationError, verify_artifact
from .live_linear_policy import (
    FEATURE_NAMES,
    LiveLinearPolicy,
    LiveLinearPolicyError,
    build_closed_bar_features,
)
from .policy import MechanicsPolicy, MechanicsPolicyConfig, MechanicsPolicyError

__all__ = [
    "ArtifactVerificationError",
    "FEATURE_NAMES",
    "LiveLinearPolicy",
    "LiveLinearPolicyError",
    "MechanicsPolicy",
    "MechanicsPolicyConfig",
    "MechanicsPolicyError",
    "verify_artifact",
    "build_closed_bar_features",
]
