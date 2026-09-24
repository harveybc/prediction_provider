# Forecast MUP Design and Test Gates

Scope: one real native forecasting provider for the five-provider M5PHET chat
workbench. The other four providers and the runtime validator have other owners.
No training, GPU, held-out scoring, external models, trades, or M5PHET edits.

Discovery: prediction_provider owns serving. Its default predict_request is an
oracle, so it is not used. The predictor E1 household successor DEV R0_s1 has
retained weights, a native factory, train-only scaler and NO_TEST_ACCESS receipt.
Use that exact factory for export, then TensorFlow SavedModel for inference.
No architecture rewrite, random-weight fallback, label replay or implicit fit.

## Top-down Gates (Designed Before Implementation)

S0-S2: actor is a local chat/runtime caller. Happy path loads an explicitly
configured bundle, submits one history window, receives a point forecast.
Alternate path compiles a bounded explicit prompt into draft2. Refuse missing
state, corrupt artifacts, wrong task/columns/shape/scale/horizon and ambiguous text.

S3 acceptance: export an existing trained DEV checkpoint; compare one DEV TRAIN
history window through native predict_on_batch, SavedModel and provider; restart
and repeat. No quality claim or held-out target is needed for adapter parity.

S4 architecture: independently installable forecast/ package, following the
repository's mechanics/ precedent. No changes to root dependencies. Lazy TF load,
CPU device, immutable bundle digest, metadata-only load result for Registry deepcopy.
Export imports the trusted, explicit predictor source; serving needs no sibling repo.

S5-S8 tests: CLI export/infer/restart, Registry entry-point registration, state
identity and tamper tests, capability combination, grammar, numeric and shape
boundaries, input perturbation, no future or labels as inputs. Missing real bundle
skips ONLY artifact integration tests, never substitutes a synthetic acceptance.

| Requirement | Test / Evidence |
| --- | --- |
| F1 real trained native engine | export parity.json + real bundle test |
| F2 Registry lifecycle and entry point | discovery test + load/infer tests |
| F3 target x horizon, units and scale | payload and schema tests |
| F4 fail closed, bounded resources | tamper, shape, finite, task, horizon tests |
| F5 explicit bounded chat grammar | valid draft2 and ambiguous prompt tests |
| F6 no training/GPU/heldout scoring | export reads Xs/train_origins/scalers only; CPU guard |
| F7 reproducible smallest CLI | README commands + isolated process replay |

DEV results do not establish calibration, benchmark success, governance acceptance
or production eligibility. A fitted-state hash identifies bytes, not scientific validity.

## Verification Outcome

F1-F7 passed within the provider scope: 54 tests including real trained-artifact
parity/restart/perturbation, tampering, grammar, actual Registry/runtime and
isolated subprocess inference. Artifact-free contract tests alone: 19 passed.
An initial external-runtime skip was resolved when the main owner supplied its
point_forecast validator. The actual web Engine, executed in the main web
environment without changing its dependencies, returned OK and did not import
TensorFlow; it used the operator-configured native CPU interpreter. No validator
was patched or mocked to turn a refusal into success.

Native and fresh-process CLI output: 0.5412255525588989 kW, absolute difference
0.0. Exact data, weights, graph and native source identities are in
`VERIFICATION.json`; the local bundle includes its own `parity.json`.
No missing checkpoint or scaler remains. Full five-provider web acceptance is
outside this component's acceptance and remains with the main agent.
