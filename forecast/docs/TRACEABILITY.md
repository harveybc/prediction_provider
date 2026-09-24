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

## Widening to Several Bundles (2026-09-24)

Problem: the area served exactly one exported bundle, so it demonstrated that the
plumbing worked and forecast nothing else. predictor declares around 31 model
plugins and ships trained example checkpoints; none of them was reachable.

Scope of this change: serve several bundles from one provider, export one further
REAL predictor checkpoint, and make provenance a condition of being served.
Still no training, GPU, held-out scoring, external model, trade or M5PHET edit,
and no write of any kind into the predictor repository.

New gates, designed before implementation:

| Requirement | Test / Evidence |
| --- | --- |
| G1 a directory of bundles enumerates all of them | `test_a_directory_enumerates_every_bundle_it_holds`, `test_slots_declare_the_union_and_nothing_beyond_it` |
| G2 a target one bundle has resolves to that bundle | `test_a_target_only_one_bundle_has_resolves_to_that_bundle` |
| G3 a target two bundles share is refused with BOTH named | `test_a_target_two_bundles_share_is_refused_with_both_named`, `test_words_and_config_must_name_the_same_fitted_state` |
| G4 a bundle without provenance is refused, not served | `test_a_bundle_that_cannot_say_where_it_came_from_is_refused` (7 cases), `test_one_unattributable_bundle_refuses_the_whole_directory` |
| G5 the single-bundle path is unchanged | `test_a_single_bundle_path_behaves_exactly_as_before`, plus the whole pre-existing suite |
| G6 the recorded household value still reproduces | `test_the_real_bundle_answers_its_recorded_value_from_inside_a_directory` |
| G7 a second REAL predictor model is served | exported bundle + its `parity.json`; `export-predictor-example` reproduces it in one command |

Design decisions worth stating, because each one had a tempting wrong answer:

- **The v1 manifest is frozen.** Its bytes are load-bearing: the retained state
  reference, `parity.json` and `example_request.json` all quote their digest.
  It is validated exactly as it was and is never rewritten to fit the widened
  contract. Everything new is schema v2, which carries its own `state_id`.
- **Ambiguity is refused, never ordered away.** Two bundles may honestly answer
  the same target at the same horizon. Picking the enumerated first would put a
  model nobody chose behind a confident number.
- **A bad bundle refuses the whole directory.** Skipping it would report a
  shorter list as if it were complete.
- **`exposure` is not copied.** `DEV_ONLY_NO_TEST_ACCESS` is a receipt a governed
  run wrote; predictor's committed examples have none and say so
  (`PREDICTOR_EXAMPLE_NO_EXPOSURE_RECEIPT`).
- **`quality` can only be `UNMEASURED`.** Nothing in this package scores a model,
  so nothing in it may publish a quality number.
- **Derived input channels come from predictor's own preprocessor**, called and
  hashed, never reimplemented; a fork would keep working after predictor changed
  and feed the graph channels it was never trained on.

Verification outcome: 89 passed, 2 skipped (from 69 passed, 2 skipped) on the
native CPU interpreter with the retained household bundle configured. The two
skips are unchanged: they are the actual-M5PHET-runtime integrations, which are
not importable from the native interpreter.

One pre-existing test was adjusted, and the reason is external to this change:
the installed `m5phet.interpret` gained an `unsupported_named` pass that refuses a
`known_unsupported` value with `UNSUPPORTED_VALUE` where it previously returned
`MISSING_PARAMETER`. The committed provider fails that assertion too, so the
assertion now accepts either refusal while still pinning what belongs to this
package: the untrained target never becomes a parameter and the refusal names the
target the bundle does have.

DEV results still do not establish calibration, benchmark success, governance
acceptance or production eligibility, for either bundle. The direction bundle in
particular carries no exposure receipt and no measured quality of any kind.
