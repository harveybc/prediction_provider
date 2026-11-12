"""CPU replay adapter for a pinned native categorical SAC inference bundle.

This adapter consumes already encoded/scaled tensors. It neither qualifies
live sources nor reconstructs missing features, and has no order authority.
"""
import hashlib
import json
from pathlib import Path
import threading

import numpy as np

from .loader import ArtifactVerificationError, verify_artifact


class CategoricalSAC:
    def __init__(self, bundle, manifest_sha256, runtime_root):
        self.bundle = Path(bundle).resolve()
        self.manifest = json.loads(verify_artifact(self.bundle / 'MANIFEST.json', manifest_sha256))
        self.manifest_sha256 = manifest_sha256
        m = self.manifest
        required = {'model.pt', 'RECIPE.json', 'MODEL_CONFIG.json', 'PROBE.npz'}
        if (m.get('schema') != 'structural_sac.inference.v1'
                or m.get('codec') != 'NOP_BUY_SELL_CLOSE_OPPOSITE_V1'
                or set(m.get('files', {})) != required):
            raise ArtifactVerificationError('CATEGORICAL_BUNDLE_CONTRACT')
        for name, sha in m['files'].items():
            path = (self.bundle / name).resolve()
            if not path.is_relative_to(self.bundle):
                raise ArtifactVerificationError('CATEGORICAL_BUNDLE_PATH')
            verify_artifact(path, sha)
        from app import structural_refit
        if not Path(structural_refit.__file__).resolve().is_relative_to(Path(runtime_root).resolve()):
            raise ArtifactVerificationError('NATIVE_RUNTIME_IMPORT_COLLISION')
        self.model, _ = structural_refit.load_bundle(self.bundle, 'cpu')
        self.columns = list(m['columns'])
        self.recipe_identity = m['recipe_identity']
        self.shape = (self.model.recipe['tensor']['window']['observations'], len(self.columns))
        self.lock = threading.Lock()
        probe = np.load(self.bundle / 'PROBE.npz', allow_pickle=False)
        replay = self._logits(probe['inputs'])
        self.probe = dict(rows=len(replay), exact=bool(np.array_equal(replay, probe['logits'])),
                          max_abs_error=float(np.max(np.abs(replay - probe['logits']))),
                          greedy_equal=bool(np.array_equal(replay.argmax(-1), probe['logits'].argmax(-1))))
        if not self.probe['exact']:
            raise ArtifactVerificationError('NATIVE_COLD_PROBE_NOT_EXACT')

    def _logits(self, windows):
        import torch
        with self.lock, torch.inference_mode():
            result = self.model.surfaces(torch.as_tensor(windows, dtype=torch.float32)).cpu().numpy()
        if result.shape != (len(windows), 3) or not np.isfinite(result).all():
            raise ValueError('CATEGORICAL_OUTPUT')
        return result

    def info(self):
        return dict(schema='prediction_provider.categorical_sac.v1', state='MODEL_LOADED',
                    model_sha256=self.manifest['files']['model.pt'],
                    manifest_sha256=self.manifest_sha256, recipe_identity=self.recipe_identity,
                    columns=self.columns, shape=list(self.shape), codec=self.manifest['codec'],
                    probe=self.probe, live_inputs_verified=False, execution_authorized=False,
                    checkpoint_qualification=self.manifest['checkpoint'])

    def replay(self, recipe_identity, columns, window):
        if recipe_identity != self.recipe_identity or columns != self.columns:
            raise ValueError('RECIPE_OR_COLUMN_ORDER_MISMATCH')
        x = np.asarray(window, dtype=np.float32)
        if x.shape != self.shape or not np.isfinite(x).all():
            raise ValueError('WINDOW_SHAPE_OR_FINITE')
        logits = self._logits(x[None])[0]
        return dict(schema='prediction_provider.categorical_replay.v1',
                    model_sha256=self.manifest['files']['model.pt'],
                    recipe_identity=self.recipe_identity,
                    input_sha256=hashlib.sha256(x.astype('<f4').tobytes()).hexdigest(),
                    logits=logits.tolist(), action=int(logits.argmax()),
                    evidence_class='REPLAY_ONLY', execution_authorized=False)
