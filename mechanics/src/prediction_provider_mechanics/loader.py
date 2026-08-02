"""Hash-verified artifact loading (ruling R1 gate for L0/L1).

Verification is mandatory and separate from loading: an artifact whose
SHA-256 does not match its declared hash never reaches a deserializer.
Loading Stable-Baselines3 zips is lazy so the verification layer works in
environments without SB3 installed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


class ArtifactVerificationError(RuntimeError):
    """The artifact bytes do not match their declared identity."""


def verify_artifact(path: str | Path, expected_sha256: str) -> bytes:
    """Return the artifact bytes only if their SHA-256 matches exactly.

    ``expected_sha256`` accepts either bare hex or the canonical
    ``sha256:<hex>`` form used by trading contracts.
    """
    expected = expected_sha256.removeprefix("sha256:").lower()
    if len(expected) != 64 or any(
        character not in "0123456789abcdef" for character in expected
    ):
        raise ArtifactVerificationError("expected hash is not sha256 hex")
    artifact_path = Path(path)
    try:
        payload = artifact_path.read_bytes()
    except OSError as error:
        raise ArtifactVerificationError(
            f"artifact unreadable: {artifact_path}: {error}"
        ) from error
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected:
        raise ArtifactVerificationError(
            f"artifact hash mismatch: expected {expected}, got {digest}; "
            "refusing to load"
        )
    return payload


def load_sb3_policy(path: str | Path, expected_sha256: str):
    """Verify then load an SB3 policy zip. Lazy import keeps the
    verification layer dependency-light; loading requires SB3 installed."""
    verify_artifact(path, expected_sha256)
    try:
        from stable_baselines3 import SAC  # noqa: PLC0415 — lazy by design
    except ImportError as error:  # pragma: no cover — env-dependent
        raise ArtifactVerificationError(
            "stable_baselines3 not installed; artifact verified but not loaded"
        ) from error
    return SAC.load(str(path))
