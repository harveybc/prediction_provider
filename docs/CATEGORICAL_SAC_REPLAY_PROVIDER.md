# Categorical SAC Provider Handoff

This isolated mechanics service loads the native categorical SAC bundle, not
an SB3 continuous SAC or the legacy linear policy. It has no broker credentials,
no order endpoint, and no claim that live features are available. This preserves
the public provider's role while the consumer builds and qualifies live feeds.

Acceptance before start: verify the externally pinned manifest hash and all
four artifact hashes, load the native runtime, reproduce every saved probe
logit exactly, reject missing/nonfinite inputs and wrong feature order, and
refuse requests attempting to label replay as live. Unit fixtures test the
interface; only the actual bundle probe establishes native numerical parity.

Use a dedicated runtime with the pinned `agent-multi` checkout ahead of any
other top-level `app` package. The loader verifies the resolved native module
is inside `runtime_root`. Do not install multiple generic `app` packages into
the running broker environment.

Config JSON (private paths supplied by the operator):

```json
{
  "bundle": "/path/to/preserved/bundle",
  "manifest_sha256": "<sha256-of-MANIFEST.json>",
  "runtime_root": "/path/to/pinned/agent-multi"
}
```

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=/path/to/pinned/agent-multi:/path/to/provider/mechanics/src \
python -m prediction_provider_mechanics.categorical_service \
  --config /path/to/private/config.json --port 8769
```

The service always binds loopback. `/v1/model` returns ordered columns, tensor
shape, native codec, model hash and probe receipt. `/v1/replay` accepts
`recipe_identity`, `columns` and one already normalized `window`. It performs
no additional scaling, clipping, missing-value fill or feature generation.
Do not reinterpret logits as calibrated uncertainty. `/health` intentionally
reports `live_ready: false`, even when the model is loaded.

The forward integrator must first qualify all live producers, their frozen
states, event/publication clocks, encoding and fixed TRAIN scaler. A future
live endpoint needs authenticated producer provenance and freshness checks;
this replay endpoint must not become a shortcut around those checks. Native
SL/TP/volume, position reconciliation and demo execution remain owned by LTS
and the existing strategy contract, not by this model adapter.
