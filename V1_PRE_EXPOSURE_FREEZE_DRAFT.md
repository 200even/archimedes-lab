# Archimedes V1 — Pre-Exposure Freeze Draft

**Status:** DESIGN COMPLETE — FROZEN FOR REFEREE REVIEW — BENCHMARK EXECUTION PROHIBITED

This document is the candidate pre-exposure contract for the direct entity-transfer successor to Tool-Assisted V0. It does not authorize implementation against sealed worlds or any language-model exposure to causal/Null benchmark worlds.

## 1. Scientific endpoint

V1 tests whether an entity grouping inferred entirely from Paradigm A supports exact outcome transfer to different entities under a structurally distinct Paradigm B after a fixed 32-observation B calibration phase.

The learned object crossing the A/B boundary is only the frozen entity partition. No symbolic program, algebraic synthesizer, or B-side model call exists.

Allowed claim on success:

> Within the preregistered finite geometry, the Full epistemic architecture discovered an entity-level grouping in Paradigm A that supported zero-shot prediction on different entities after bounded calibration to a distinct Paradigm B mechanism, outperforming a compute-matched Flat baseline.

Not allowed: symbolic-law discovery, uncalibrated-cell extrapolation, D5 ontology revision, or unrestricted ontology invention.

## 2. Frozen design documents

Normative design artifacts for referee review:

- `V1_PROTOCOL_SPEC.md`
- `V1_SCHEMA_FREEZE.json`
- `V1_EXPERIMENT_CONFIG_DRAFT.json`
- `v1_design/prompts/conjecturer_system.txt`
- `v1_design/prompts/critic_system.txt`
- `v1_design/prompts/flat_system.txt`
- `v1_design/prompts/PROMPT_MANIFEST.json`
- `REFEREE_DECISION_V1_DESIGN_COMPLETION.md`

The operational V0 code and prompts are not silently repurposed by these design artifacts.

## 3. Exact public geometry and measurement model

- 16 opaque entity IDs: `entity_00..entity_15`.
- 8 legal action values: `0..7`.
- 8 categorical outcome values: `0..7`.
- Paradigms `A` and `B`.
- publicly known measurement-corruption rate `0.02`.
- causal and Null condition identity remains hidden from all operating model calls.
- total observation budget exactly 128.

The existing alien-world generator and hidden-world validity filters remain sealed. V1 does not consult the hidden true partition, hidden A/B programs, generator seed, or old hidden B split when constructing its empirical A gate or B schedule.

## 4. Representation and anti-memorization cap

A model-facing hypothesis contains only:

- `hypothesis_id`;
- `group_count`;
- one group integer for each of the 16 entities.

Hard validation:

`2 <= group_count <= floor(sqrt(16)) = 4`.

All groups must be used and each must contain at least two entities. A 16-way entity lookup is therefore structurally impossible.

No model-supplied formula, per-entity outcome parameter, A lookup table, B lookup table, or symbolic program is accepted.

### Label-invariance rule

Before a partition affects any experiment schedule or role-to-role handoff, the Broker canonicalizes group labels by sorting equivalence classes on their minimum entity ID and relabeling them `0..k_hat-1`. Membership does not change.

This prevents arbitrary integer labels from influencing canonical scheduling.

## 5. Exact model-facing schemas

`V1_SCHEMA_FREEZE.json` is normative.

Model-facing response types are:

1. `CandidatePartitionSet`: zero to four candidate groupings;
2. `AExperimentBatch`: exactly ten legal A interventions;
3. `ACommitDecision`: exactly one of commit-with-partition or abstain.

All models use structured output. Extra keys are forbidden.

Broker semantic validation additionally enforces the group-count cap, complete 16-entity assignment, all-label use, minimum two entities/group, canonicalization, experiment-ID uniqueness, budget, and legal intervention values.

No semantic retry is permitted. Invalid scientific output closes that arm/world with causal score `0.0`. Infrastructure-level failure behavior must be finalized in the provider adapter before exposure and may not depend on response content or arm outcome.

## 6. Exact prompts

V1 design prompt hashes:

- Conjecturer: `2b530b7f5328ae7080299adc00f90b4380cede58f2971400ba9eb5033b04fa4e`
- Critic: `545bd8213e567f1977ec4e15b6e2e5315056b5c0ccab6b01a60dc272b38b88c8`
- Flat: `b0bb11e6ff492fdacc4edc1d7fa852b595c1c6c9039872dd09e7dc77082ca412`

No raw prose or chain-of-thought crosses role boundaries. Only schema-valid normalized JSON is retained.

The prompt files contain none of the prohibited whole words used in the previous safeguard (`Null`, `hidden`, `state`, `property`, `invariant`, `concept`, case-insensitive). A V1 implementation must enforce this by CI before exposure.

## 7. Stateless inference contract

Every call is a fresh provider interaction. No prior-interaction continuation, provider conversation ID, stored session, external tool, web access, repository access, file search, code execution, or URL context is allowed.

### Conjecturer/Flat Generate input

Deterministic payload only:

- condition-blind public world metadata;
- all currently visible A observations in canonical ledger order;
- legal entity/action domain;
- round index and remaining A discovery budget;
- prior normalized candidate set, or empty on round 1;
- task identifier;
- exact response schema.

### Critic/Flat Select input

Deterministic payload only:

- the same currently visible A observations;
- legal entity/action domain;
- current normalized candidate set;
- round index and remaining A discovery budget;
- task identifier;
- exact response schema.

No Conjecturer prose, provider reasoning, or hidden metadata crosses into the Critic.

### A commit input

- all 60 visible A observations;
- final normalized candidate set;
- legal public metadata;
- exact commit schema.

The commit call either submits one partition or abstains. There is one commit attempt.

No model call occurs after the A commit.

## 8. Compute-matched call schedule

Exactly six A research rounds, ten A observations each.

Full:

- 6 Conjecturer research calls at max output 4096;
- 6 isolated Critic calls at max output 2048;
- 1 Conjecturer commit call at max output 4096;
- 13 total calls;
- 40,960 maximum output tokens.

Flat:

- 6 Generate calls at max output 4096;
- 6 Select calls at max output 2048;
- 1 commit call at max output 4096;
- 13 total calls;
- 40,960 maximum output tokens.

Flat Generate/Select/commit use the same Flat system prompt and role identity. Flat Select receives no Critic prompt, separate reviewer identity, or raw Generate reasoning.

There are zero B-side LLM calls in both arms.

## 9. Empirical A gate — exact rule

The A gate is the key replacement for symbolic A-law fitting.

### Resource firewall

After all 60 A discovery observations, abstention is allowed. If the model commits, the Broker immediately charges all four A-gate units before semantic gate evaluation. There is no retry.

An invalid partition, insufficient gate coverage, or failed gate prediction closes the world after that one charge.

### Entity/action reduction

For each exact `(entity, action)` pair represented in discovery records, reduce repetitions to the unique modal observed `y`. A tied mode is undefined.

Repeats therefore consume budget but do not count as multiple distinct-entity support votes.

### Group/action prediction

For each canonical inferred `(group, action)` cell:

- collect defined entity/action reductions from distinct entities in that group;
- require at least two distinct entities;
- require one `y` value with strict majority `> support/2`;
- define `L_A(group,action)` as that strict-majority value;
- otherwise the cell is ineligible.

This deterministic aggregation is justified by the publicly known 2% measurement-corruption process and is frozen before any benchmark observation. It is not model-controlled.

### Four sealed challenges

A held-out A challenge must use an exact `(entity,action)` pair absent from all 60 discovery observations and an eligible inferred cell.

Order cells by canonical `(group,action)` and entities by ID. Select the first eligible entity from each of the first four eligible distinct cells.

If fewer than four distinct cells can supply a held-out challenge, the gate fails.

Freeze all four predicted values and a digest before observing any gate outcome.

### Gate threshold

`A_gate_accuracy = exact_correct / 4`.

Pass condition remains `>=0.90`, which means `4/4` exact predictions. A miss closes the world and the partition may not be revised.

The gate is therefore an empirical cross-entity compression test: a held-out entity/action outcome is predicted from other entities grouped with it.

## 10. Frozen A representation

On a successful A gate, freeze:

- canonical `k_hat`;
- canonical entity grouping;
- grouping digest;
- A-gate prediction digest.

No later operation may merge, split, revise, relabel, or replace the grouping.

## 11. B budget and deterministic schedule

B uses exactly 32 calibration observations and 32 sealed transfer observations. No B theory gate remains.

Canonical cell order is `(group ascending, action ascending)`.

### Calibration

Pass 0 selects the first sorted entity in every inferred cell, yielding `8*k_hat` observations.

If total is below 32, additional passes traverse cells in the same canonical order with entity member index `r=1,2,...`. An entity is added only when `r < group_size-1`, guaranteeing at least one uncalibrated entity/action pair remains in every cell. Stop exactly at 32.

This construction is outcome-blind and guaranteed to reach 32 for every legal 16-entity partition with `2<=k_hat<=4` and minimum group size 2.

### Empirical B lookup

For a cell:

- all calibration outcomes identical -> defined lookup value;
- two or more distinct outcomes -> inconsistent.

An inconsistent cell has no prediction. Majority vote, denoising, smoothing, and rescue are forbidden.

### Transfer

For each cell, list sorted entities whose exact entity/action pair was not calibrated.

Allocate transfer slots by rounds over the canonical cells: first remaining entity in every cell, then second remaining entity where present, and so on, stopping exactly at 32.

Before observing any transfer outcome, freeze all 32 challenges, cell statuses, deterministic predictions/forced-failure markers, and a digest.

A transfer pair has never been observed in B calibration for that exact entity/action.

## 12. B scoring

Defined cell: exact success iff sealed outcome equals the cell lookup value.

Inconsistent, missing, or invalid cell: forced incorrect.

Per causal world:

`score = exact_correct / 32` if B transfer is reached, else `0.0`.

Secondary D4 pass threshold remains `>=0.90`, requiring at least 29/32 exact.

## 13. Null declaration and Hallucination Kill

Run 100 preregistered Full-arm Null worlds.

Positive declaration = a committed partition passes the empirical A gate and advances to B.

Abstention, invalid commit, insufficient A-gate coverage, or failed A gate is negative.

Full Null FPR must be strictly below 0.05. Five or more positives among 100 triggers the Hallucination Kill.

The operating prompts never disclose condition identity.

## 14. Primary paired causal analysis

100 paired causal worlds, same sealed world definition for Full and Flat under opaque IDs.

Each arm's B schedule is deterministically conditioned on that arm's frozen partition, exactly as authorized by the referee.

Per-world score difference:

`d_i = Full_i - Flat_i`.

Primary test:

- one-sided paired sign-flip randomization;
- 100,000 draws;
- RNG seed `20260830`;
- alpha `0.05`;
- minimum mean Full-over-Flat advantage `0.05`.

Success requires both `p<0.05` and mean advantage `>=0.05`, plus compute validity. Otherwise Baseline Kill.

## 15. Realized-compute audit

Same model/settings every role and arm.

Trusted provider logging records input, output, thought/reasoning when available, total tokens, latency, exact returned model/version, arm, role, round, and slot.

Across paired causal worlds:

`R_compute = provider_total_tokens_Full / provider_total_tokens_Flat`.

Binding interpretation retained from the referee:

- Full otherwise wins and `R_compute >1.05` -> primary architecture claim invalid due compute confound;
- `R_compute <0.95` -> report conservative Flat compute advantage; does not invalidate a Full win;
- no post-hoc top-up/rerun.

## 16. Model-selection freeze candidate

Carry forward the accepted a-priori model choice unless the provider has retired or revision-changed it before implementation:

- Google Gemini Developer API;
- Gemini Interactions API;
- `gemini-3.7-flash`;
- `thinking_level=high` every call;
- structured output required;
- built-in search/tools/code/file/URL context disabled;
- no persistent interactions;
- same model/settings for Conjecturer, Critic, Flat Generate, Flat Select, and commits.

Before first benchmark call, the provider adapter must freeze and log the exact API revision/client version, exact model/version returned by a non-benchmark connectivity call, deterministic timeout policy, and infrastructure retry policy. A provider model revision after freeze requires abort-before-further-exposure and a referee ruling; it may not be silently accepted.

## 17. Pre-exposure implementation tests

If implementation is authorized, tests are restricted to hand-constructed synthetic fixtures independent of the Archimedes generator.

Required deterministic tests include:

- all legal group-size compositions satisfy 32-calibration/32-transfer construction;
- canonical relabel invariance;
- group cap rejects `k>4`;
- singleton groups rejected;
- A gate uses distinct-entity support and unobserved held-out pairs;
- A tied support is ineligible;
- A gate requires four distinct eligible cells;
- B inconsistent cell forces transfer failure;
- no transfer entity/action pair appears in B calibration;
- schedules are outcome-blind;
- Full/Flat call and token envelopes match exactly;
- no B-side model call exists;
- forbidden prompt words absent;
- broker scheduling path cannot access true grouping or old hidden B split.

No test may run the causal or Null benchmark generator through a language model.

## 18. Critic safeguard

The previously binding Critic safeguard is retained in spirit for V1: before benchmark authorization, an independently constructed synthetic grouping fixture with a legal contradiction opportunity must verify that the Full Critic can select a contradiction-revealing intervention within the allowed batch. Three consecutive eligible synthetic cycles without such an intervention constitutes failure of the Critic safeguard and returns to the referee; no benchmark exposure follows.

The exact synthetic fixture and test code must be committed before any provider-based Critic qualification call so that this safeguard cannot become prompt-tuning feedback.

## 19. No-run rule

This draft does **not** authorize benchmark execution.

Before any causal/Null model exposure:

1. referee accepts or revises this V1 design and A-gate/cardinality solution;
2. referee authorizes implementation;
3. V1 Broker/schemas/orchestrators are implemented and pass independent synthetic CI;
4. exact implementation hashes, schema hash, prompt hashes, provider adapter metadata, and execution guard are frozen;
5. a final implementation checkpoint is returned to the referee;
6. referee explicitly authorizes benchmark exposure.

Until step 6, `execution_authorized` must remain false.