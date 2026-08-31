# Archimedes V0 — Pre-Exposure Freeze Draft

**Status:** IMPLEMENTED DRAFT — NOT AUTHORIZED FOR BENCHMARK EXPOSURE  
**Predecessor:** V0.1.3 safeguards authorized for agent-layer implementation only.

The code deliberately blocks `ArchimedesOrchestrator.run()` and `FlatBaselineOrchestrator.run()` unless an explicit `execution_authorized=True` flag is supplied. That flag may not be enabled for benchmark work until this document is completed and the referee authorizes exposure.

## 1. Exact role prompts

The exact prompt files are:

- `prompts/conjecturer_system.txt` — SHA-256 `e5d3bcefd83d39d98a2f378b42393ea1c6c9edc435fbe8ec483d7472f7fae327`
- `prompts/critic_system.txt` — SHA-256 `a43fe306356c2384f86c6cecc928f49ec09aa83a7a83e5870c90fe8f19b28673`
- `prompts/flat_system.txt` — SHA-256 `97f12507a99c20da9a7251e93ae4b9e3734a85c8d2f641ba7830397e368b6033`

The instruction text contains none of the whole words `Null`, `hidden`, `state`, `property`, `invariant`, or `concept`. A CI test enforces this. The model still receives the machine-readable bounded execution schema because V0 explicitly tests D4 inside that preregistered representation language.

No raw model prose or reasoning crosses role boundaries. Only schema-valid JSON is retained.

## 2. Stateless inference contract

Every Conjecturer, Critic, and Flat-agent invocation is a fresh provider request. No conversation/session identifier or prior raw response may be reused. Role interfaces accept only:

- the fixed system prompt;
- a deterministic JSON payload for the current call;
- the exact response JSON schema;
- the call-specific maximum output-token cap.

Provider adapters must not expose repository source, generator source, validation reports, ground truth, seeds, sealed transfer outcomes, web browsing, or prior conversations.

Transport failures may not be converted into semantic retries. The exact infrastructure retry policy is still to be frozen with the provider/model selection below.

## 3. Full-arm call schedule

The deterministic schedule is:

### A

Six research rounds. Each round performs:

1. one Conjecturer call;
2. one Critic call;
3. exactly 10 Broker interventions selected by the Critic.

This consumes 60 visible A interventions.

Then exactly one Conjecturer A-commit call occurs. It either submits one Theory AST to the one-shot A gate or abstains.

### B

If A survives, four research rounds follow. Each performs:

1. one Conjecturer call;
2. one Critic call;
3. exactly 7 Broker interventions on B-calibration entities.

This consumes 28 visible B-calibration interventions.

Then exactly one Conjecturer B-commit call occurs. If the one-shot B gate survives, the Broker commits 32 theory-derived sealed transfer predictions and executes the sealed transfer evaluation.

Maximum Full-arm model calls per completed D4 world:

- Conjecturer: 11
- Critic: 10
- total: 21

The Broker epistemic-cycle count is exactly 10, below the preregistered maximum of 12.

## 4. Flat LLM+synthesis baseline

The Flat arm receives the **identical Broker information budget**:

- 60 A observations;
- one four-unit A gate;
- 28 B-calibration observations;
- one four-unit B gate;
- 32 sealed B-transfer outcomes.

It receives the same public metadata, machine-readable program schema, candidate-synthesis tool implementation, and restrictions on external information.

It does not receive a separate adversarial Critic role or persistent multi-model competition. One flat call selects each intervention batch, followed by one A commit call and one B commit call.

Maximum Flat calls per completed D4 world: 12.

To make this comparison conservative with respect to model-generation capacity, the current interface permits up to 8192 output tokens per Flat call versus 4096 per Conjecturer call and 2048 per Critic call. Maximum theoretical output capacity therefore favors the Flat baseline.

**BLOCKER BEFORE EXPOSURE:** the concrete `CandidateSynthesizer` implementation/version and exact per-round invocation policy must be frozen. `NoSynthesis` is development-only and is not an authorized comparative baseline.

## 5. Functional-minimality diagnostic

Immediately after a successful A freeze, both Full and Flat orchestration compute the complete A response signature for every declared label across all eight actions.

Record:

- declared cardinality;
- effective cardinality (number of unique signatures);
- whether the representation is functionally minimal;
- redundant label groups;
- SHA-256 digest of the signature table.

This diagnostic uses only the committed A theory and no generator truth.

After unblinding, also report the secondary exact-cardinality diagnostic:

`delta_k = k_hat - k_true`.

Neither diagnostic replaces the primary D4 transfer endpoint.

## 6. Abstention and Null false positives

Abstention is available only after all 60 A observations and before the one-shot A theory gate.

A positive declaration for Null-world FPR is operationally:

> the A theory gate accepts and advances the run to B calibration.

An abstention or rejected A gate is not a positive declaration.

The Full-arm Null-world FPR must remain strictly below 0.05. With 100 preregistered Null worlds, 5 or more positive declarations triggers the Hallucination Kill.

The operating prompts do not disclose that a noise-only condition exists.

## 7. Primary cross-world analysis

Experimental unit: **world**, never an individual transfer intervention.

Causal sample:

- 100 paired causal worlds for Archimedes-Full and Flat LLM+synthesis.
- The two arms use paired generator seeds and the same sealed world definitions.
- Arm-visible world IDs remain opaque.

Per-world primary score:

- sealed B-transfer exact accuracy if the run reaches transfer;
- `0.0` if the arm abstains on a causal world, fails either theory gate, emits schema-invalid scientific output, exhausts its allowed schedule, or otherwise fails to produce a transfer-qualified model.

Primary comparison:

- one-sided paired sign-flip randomization test over the 100 per-world accuracy differences;
- 100,000 sign-flip draws;
- fixed RNG seed `20260830`;
- alpha `0.05`;
- preregistered minimum mean Full-over-Flat advantage `0.05`.

Primary success requires **both** `p < 0.05` and mean paired advantage `>= 0.05`.

The Baseline Kill fires if primary success is not achieved.

Secondary reporting:

- mean and distribution of per-world transfer accuracy;
- fraction of worlds meeting the individual 0.90 D4 threshold;
- exact-cardinality recovery;
- functional-minimality rate;
- abstention and gate-failure rates;
- experiment-selection coverage.

No transfer-measurement-level significance test may be substituted for the world-level primary analysis.

## 8. Model and sampling freeze

The following fields are intentionally unresolved and therefore block exposure:

- provider: **UNFROZEN**
- exact model snapshot/ID: **UNFROZEN**
- API/version date: **UNFROZEN**
- temperature: proposed `0`
- top-p: proposed `1`
- provider seed behavior: **UNFROZEN**
- transport retry policy: **UNFROZEN**
- timeout: **UNFROZEN**

The same model snapshot must be used for Full Conjecturer, Full Critic, and Flat baseline unless a later referee-approved design explicitly tests heterogeneous roles.

## 9. Tool-access freeze

Authorized role-facing inputs are limited to:

- condition-blind public world metadata;
- visible Broker observations;
- legal entity/action lists for the current phase;
- normalized schema-valid candidate models;
- the exact response schema;
- remaining public resource budget;
- the frozen A model during B;
- outputs of the identically configured visible-data-only synthesis tool once that tool is frozen.

Forbidden:

- internet/web;
- GitHub/repository browsing;
- generator or hidden runtime source;
- validation reports;
- seed or condition metadata;
- ground-truth assignments/program parameters;
- sealed B outcomes before closure;
- raw reasoning from another role;
- previous conversational context.

## 10. No-run rule

No benchmark model call is authorized by this draft. Before exposure:

1. freeze the concrete model snapshot and provider parameters;
2. freeze the concrete synthesis implementation and invocation schedule;
3. freeze infrastructure failure/retry handling;
4. regenerate and hash the prompt/config manifest;
5. submit the completed pre-exposure freeze to the referee;
6. receive explicit exposure authorization.

Until then, CI/tests may use deterministic fake backends and development-only `NoSynthesis`, but no causal or Null benchmark world may be supplied to an LLM.
