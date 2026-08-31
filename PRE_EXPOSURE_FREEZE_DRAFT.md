# Archimedes V0 — Pre-Exposure Freeze Draft

**Status:** REVISED DRAFT — NOT AUTHORIZED FOR BENCHMARK EXPOSURE  
**Current referee ruling:** HOLD — revise synthesizer qualification distribution and Flat-baseline compute parity.

The code continues to block `ArchimedesOrchestrator.run()` and `FlatBaselineOrchestrator.run()` unless an explicit `execution_authorized=True` flag is supplied. That flag may not be enabled for benchmark work until the completed pre-exposure protocol is explicitly authorized.

## 1. Exact role prompts

The exact draft prompt files are:

- `prompts/conjecturer_system.txt` — SHA-256 `e5d3bcefd83d39d98a2f378b42393ea1c6c9edc435fbe8ec483d7472f7fae327`
- `prompts/critic_system.txt` — SHA-256 `a43fe306356c2384f86c6cecc928f49ec09aa83a7a83e5870c90fe8f19b28673`
- `prompts/flat_system.txt` — SHA-256 `97f12507a99c20da9a7251e93ae4b9e3734a85c8d2f641ba7830397e368b6033`

The instruction text contains none of the whole words `Null`, `hidden`, `state`, `property`, `invariant`, or `concept`. A CI test enforces this. No raw model prose or reasoning crosses role boundaries; only schema-valid JSON is retained.

## 2. Stateless inference contract

Every Conjecturer, Critic, and Flat invocation is a fresh provider request. No conversation/session identifier or prior raw response may be reused. Role interfaces accept only the fixed system prompt, a deterministic JSON payload, the exact response schema, and the call-specific output-token ceiling.

Provider adapters must not expose repository source, generator source, validation reports, ground truth, seeds, sealed transfer outcomes, web browsing, or prior conversations. Semantic failures may not be retried. Infrastructure retry handling remains a pre-exposure blocker.

## 3. Full-arm call schedule

There are six A research rounds and four B research rounds. Each research round performs one Conjecturer call followed by one isolated Critic call, then executes exactly the preregistered intervention batch: 10 interventions per A round and 7 per B round.

After the six A rounds, one Conjecturer A-commit call either submits one Theory AST to the one-shot A gate or abstains. After the four B rounds, one Conjecturer B-commit call submits the final frozen-compatible Theory AST.

A completed D4 world therefore permits exactly:

- Conjecturer calls: **12** = 6 A research + 1 A commit + 4 B research + 1 B commit;
- Critic calls: **10** = 6 A research + 4 B research;
- total model calls: **22**.

The earlier draft incorrectly stated 11 Conjecturer calls / 21 total. This was an arithmetic documentation error; the implemented schedule itself has always implied 12 + 10 = 22.

Frozen output-token ceilings proposed for each Full slot:

- Conjecturer research or commit: **4096**;
- Critic research: **2048**.

Thus the maximum Full output-token envelope for a completed world is:

`12 * 4096 + 10 * 2048 = 69,632` tokens.

The Broker epistemic-cycle count remains exactly 10, below the preregistered maximum of 12.

## 4. Compute-matched Flat LLM+synthesis baseline

The Flat arm receives the identical Broker information budget: 60 A observations, one four-unit A gate, 28 B-calibration observations, one four-unit B gate, and 32 sealed B-transfer observations.

The previous one-call-per-round Flat design is withdrawn because it did not adequately match inference compute.

### Matched two-slot research round

For each of the same ten research rounds, Flat receives exactly two fresh calls using the **same Flat system prompt and same role identity**:

1. **Flat Generate** — maximum 4096 output tokens; returns a schema-valid `CandidateSet` using the current visible records and the identically configured synthesis output.
2. **Flat Select** — maximum 2048 output tokens; receives the current visible records plus only the normalized `CandidateSet` from Flat Generate and returns the required `ExperimentBatch`.

Flat Select is not given the Critic prompt, an adversarial persona, a falsification objective, or Critic conversation history. It is simply a second stateless call by the same single-role baseline. Raw reasoning from Flat Generate is not passed to Flat Select.

After research, Flat receives one 4096-token A-commit call and, if A survives, one 4096-token B-commit call.

A completed Flat world therefore permits exactly:

- Flat Generate calls: **10**;
- Flat Select calls: **10**;
- Flat commit calls: **2**;
- total model calls: **22**.

Its maximum output-token envelope is exactly:

`10 * 4096 + 10 * 2048 + 2 * 4096 = 69,632` tokens.

This exactly matches the Full arm's call count and maximum output-token allocation. Generate and Conjecturer slots share the same 4096 ceiling; Select and Critic slots share the same 2048 ceiling; commit slots are also matched.

The independent variable is therefore not the number of model calls or allocated output capacity. It is the presence in Full of a separately prompted, causally isolated adversarial Critic rather than same-role Flat self-refinement.

### Thinking-compute accounting

The proposed model is Gemini 3.7 Flash with `thinking_level=high` for **every** Full and Flat call. Gemini's thinking level is a relative reasoning allowance rather than an exact thought-token budget, so realized thought-token consumption cannot be forced to equality prospectively.

For every call the provider adapter must record, without exposing it to either arm:

- input tokens;
- output tokens;
- thought tokens;
- provider-reported total tokens;
- latency;
- model/version metadata returned by the provider.

Across the 100 paired causal worlds, define aggregate realized-compute ratio:

`R_compute = total_provider_tokens_Full / total_provider_tokens_Flat`.

Proposed validity band: `0.95 <= R_compute <= 1.05`.

If Full exceeds the upper bound, a nominal Full performance win may **not** be interpreted as evidence for the epistemic architecture because raw realized compute remains a plausible confound. No post-hoc top-up calls or reruns are allowed to repair the ratio after outcomes are known. If Flat exceeds the upper reciprocal bound, that fact is reported as a conservative compute advantage for Flat. The referee is specifically asked to rule on whether this 5% aggregate validity band is appropriate or whether matched call/configuration envelopes alone are sufficient.

## 5. CandidateSynthesizer boundary

The synthesizer may perform deterministic law fitting but may not search latent organization.

The LLM must supply the proposed `k_hat` and entity-to-label assignments. The synthesizer may not create, alter, merge, split, optimize, or search those assignments. Given that fixed representation and visible observations, it may search only for executable programs in the public Theory AST language.

The same concrete synthesizer, candidate count, search ceiling, invocation schedule, and visible inputs must be used identically in Full and Flat.

`NoSynthesis` remains development-only and is not authorized for comparative runs.

## 6. Synthesizer qualification distribution

The synthesizer search ceiling may not be selected from Archimedes benchmark performance or from a corpus sampled with Hidden World priors.

The qualification corpus will contain **1,000 IID ASTs** sampled from a dedicated qualification grammar `G_Q`, wholly independent of the Hidden World generator's templates, weights, and sampling code.

### Finite qualification grammar

To make "uniform over all valid ASTs" mathematically well-defined, `G_Q` fixes all otherwise open identifier choices:

- variables are exactly the two canonical symbols `{q, a}`;
- constants are exactly `{0,...,7}`;
- unary/binary operator vocabulary is exactly the public Theory AST operator vocabulary, including distractors;
- `rotl` shift is one of its schema-valid finite shifts;
- permutation mappings range over all `8!` schema-valid permutations;
- maximum AST depth is 5;
- no free-form identifiers, metadata, entity assignments, A/B transfer structure, or world-generator templates are part of `G_Q`.

Sampling is **uniform over canonical syntactic ASTs of depth <= 5**: each distinct canonical syntax tree in this finite grammar has equal probability. The sampler must use exact dynamic-programming subtree counts / rank-unrank-equivalent weighting. It may not choose a root operator uniformly and recurse, because that would induce a nonuniform distribution over complete ASTs.

The qualification sampler must be implemented in a module that does not import the Hidden World generator or its template distributions. Its RNG seed and generated corpus digest will be frozen before qualification.

### Qualification endpoint

For each sampled AST, visible observations are generated directly from that AST with the already frozen finite domain; the latent mapping is supplied rather than discovered. There is no cross-paradigm transfer task, no Null condition, and no Full-vs-Flat comparison.

We will test increasing deterministic enumeration ceilings and choose the **smallest fixed ceiling** at which the synthesizer recovers an observationally equivalent explanatory program on at least 95% of the 1,000 qualification cases. Only this engineering criterion may choose the ceiling. The selected ceiling, implementation SHA, corpus digest, and qualification result are then frozen before any Archimedes model exposure.

## 7. Functional-minimality diagnostic

Immediately after a successful A freeze, both Full and Flat compute the complete A response signature for every declared label across all eight actions and record declared cardinality, effective cardinality, whether the representation is functionally minimal, redundant label groups, and a SHA-256 digest of the signature table.

After unblinding, report `delta_k = k_hat - k_true` as a secondary diagnostic. Neither measure replaces the primary D4 endpoint.

## 8. Abstention and Null false positives

Abstention is available only after all 60 A observations and before the one-shot A theory gate. A Null-world positive declaration is a Broker-accepted A theory that advances to B calibration. Abstention or a rejected A gate is not a positive declaration.

The Full-arm Null false-positive rate must remain strictly below 0.05. With 100 preregistered Null worlds, 5 or more positive declarations triggers the Hallucination Kill. The operating prompts do not disclose that a noise-only condition exists.

## 9. Primary cross-world analysis

The experimental unit is the **world**, never an individual transfer intervention.

Causal sample: 100 paired causal worlds, with Full and Flat using the same sealed world definitions under opaque arm-visible IDs.

Per-world score is sealed B-transfer exact accuracy if the run reaches transfer, otherwise `0.0` for causal-world abstention, theory-gate failure, schema-invalid scientific output, schedule failure, or failure to produce a transfer-qualified model.

Primary comparison:

- one-sided paired sign-flip randomization test over 100 per-world accuracy differences;
- 100,000 sign-flip draws;
- RNG seed `20260830`;
- alpha `0.05`;
- minimum mean Full-over-Flat advantage `0.05`.

Primary success requires both `p < 0.05` and mean paired advantage `>= 0.05`, subject also to the compute-parity validity rule if that rule is authorized. Failure of the primary comparison triggers the Baseline Kill.

Secondary reporting includes transfer distributions, 0.90-D4 pass rate, exact-cardinality recovery, functional-minimality rate, abstention/gate-failure rate, intervention coverage, and provider-token/latency usage by arm.

## 10. Model selection freeze

A priori model selection is proposed as:

- provider: **Google Gemini Developer API**;
- model ID: **`gemini-3.7-flash`** stable identifier;
- API surface: **Gemini Interactions API**;
- thinking level: **high** for every Full and Flat call;
- structured output: required;
- built-in tools/search/code execution/file search/URL context: disabled;
- persistent interactions / previous-interaction continuation: prohibited.

No multi-model tournament is permitted. The same model ID and inference configuration must be used for Conjecturer, Critic, Flat Generate, Flat Select, and commit calls.

Gemini 3.7 Flash does not require the deprecated temperature/top-p/top-k controls proposed in the earlier draft; these are removed rather than tuned. The precise API revision/header, provider seed behavior, timeout, and transport retry policy remain unresolved blockers before exposure.

## 11. Tool-access freeze

Authorized role-facing inputs are limited to condition-blind public metadata, visible Broker observations, legal current-phase actions/entities, normalized schema-valid candidate models, exact response schemas, remaining public resource budget, the frozen A model during B, and outputs of the identically configured visible-data-only synthesizer once frozen.

Forbidden: internet/web, GitHub/repository browsing, generator/runtime source, validation reports, seed/condition metadata, ground-truth assignments or programs, sealed B outcomes before closure, raw reasoning from another role, or previous conversational context.

## 12. No-run rule

No benchmark model call is authorized by this draft. Before exposure:

1. obtain referee acceptance of the uniform synthesizer-qualification rule and compute-matched Flat design;
2. implement and qualify the concrete synthesizer under the approved rule;
3. update the Flat orchestrator to the approved matched two-slot schedule;
4. freeze Gemini API revision, timeout, seed behavior, and infrastructure retry handling;
5. regenerate and hash the prompt/config manifest;
6. submit the completed pre-exposure freeze to the referee;
7. receive explicit benchmark-exposure authorization.

Until then, CI/tests may use deterministic fake backends and development-only `NoSynthesis`, but no causal or Null benchmark world may be supplied to a language model.