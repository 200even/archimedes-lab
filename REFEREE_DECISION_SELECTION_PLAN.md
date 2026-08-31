# Referee Decision — Model/Synthesizer Selection Plan

**Decision:** ACCEPT SELECTION PLAN

The revised selection plan closes the two previously identified vulnerabilities: qualification-distribution leakage and compute mismatch between Archimedes-Full and the Flat baseline.

## Accepted qualification distribution

The synthesizer qualification corpus must be generated independently of Hidden World priors.

Binding requirements:

- 1,000 qualification ASTs;
- uniform probability over complete canonical syntax trees in the dedicated qualification grammar up to depth 5;
- exact dynamic-programming subtree counts / equivalent rank-unrank weighting;
- no Hidden World generator sampling weights, templates, seeds, or benchmark metadata;
- public Theory AST operator vocabulary, including same-domain distractors;
- qualification only measures deterministic synthesis competence and does not contain the A/B transfer task, Null condition, or latent-partition search.

The qualification sampler may be used to choose only the deterministic synthesis search ceiling. The selected ceiling must be frozen before any Archimedes benchmark model exposure.

## Accepted compute-matched baseline

For a completed world, both Full and Flat receive exactly 22 model calls and the same maximum output-token envelope of 69,632 tokens.

Full:

- 12 Conjecturer calls at 4,096 output tokens each;
- 10 Critic calls at 2,048 output tokens each.

Flat:

- 10 same-role Generate calls at 4,096 output tokens each;
- 10 same-role Select calls at 2,048 output tokens each;
- 2 commit calls at 4,096 output tokens each.

Flat Select must not receive the adversarial Critic prompt, a falsification persona, Critic history, or raw Generate reasoning. It is a stateless same-role refinement step.

## Mandatory realized-compute audit

All Full and Flat calls use the same model and `thinking_level=high`. Because realized thought-token consumption is provider-dynamic, the trusted adapter must record per-call provider usage metadata without exposing it to either arm.

Define:

`R_compute = total_provider_tokens_Full / total_provider_tokens_Flat`.

The 5% audit band is binding. In particular:

- if Full nominally outperforms Flat but `R_compute > 1.05`, the primary architecture claim is invalidated because excess realized compute remains a plausible explanation;
- `R_compute < 0.95` is reported as a conservative compute advantage for Flat and does not invalidate a Full win;
- no post-hoc top-up calls, outcome-dependent reruns, or compute equalization are permitted.

## Authorization

Authorized now:

- implement the concrete enumerative synthesizer;
- generate the 1,000-AST uniform qualification corpus and determine the deterministic search ceiling;
- update the Flat orchestrator to the two-slot compute-matched schedule.

Still prohibited:

- exposing any causal or Null benchmark world to a language model;
- benchmark prompt tuning;
- D4 comparative runs;
- changing selection rules based on benchmark outcomes.

Benchmark execution remains blocked until a completed pre-exposure freeze is submitted and explicitly authorized.