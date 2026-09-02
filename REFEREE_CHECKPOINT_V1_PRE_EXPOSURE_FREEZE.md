# Archimedes — Referee Checkpoint: V1 Pre-Exposure Design Freeze

**Status:** DESIGN COMPLETION SUBMITTED — IMPLEMENTATION AND BENCHMARK EXPOSURE NOT AUTHORIZED

## Executive summary

The V1 design is now complete at the protocol level. Symbolic synthesis is absent. The only learned object crossing A to B is a bounded entity partition.

This checkpoint resolves the mandatory missing link from the prior ruling: the **Empirical A Gate** and the hard anti-memorization cardinality bound.

Normative supporting documents:

- `V1_PROTOCOL_SPEC.md`
- `V1_PRE_EXPOSURE_FREEZE_DRAFT.md`
- `V1_SCHEMA_FREEZE.json`
- `V1_EXPERIMENT_CONFIG_DRAFT.json`
- `v1_design/prompts/PROMPT_MANIFEST.json`
- `REFEREE_DECISION_V1_DESIGN_COMPLETION.md`

No V1 benchmark model call has occurred.

## 1. Solution to the Empirical A-Gate problem

After exactly 60 A discovery observations, a non-abstaining arm commits one partition satisfying the hard representation rules.

The one-shot four-unit A gate is then charged **before** semantic gate validation. No resubmission is possible.

For each exact `(entity,action)` pair observed during discovery, repetitions are reduced to a unique modal outcome; a tie is undefined. This prevents repeated observations of one entity from numerically masquerading as cross-entity support.

For each inferred `(group,action)` cell, the Broker then:

1. collects defined reductions from distinct entities in that group;
2. requires at least two distinct supporting entities;
3. requires one outcome with strict majority `> support/2`;
4. defines that outcome as the deterministic empirical A prediction for the cell.

The known public measurement-corruption rate is 2%, so this aggregation is a frozen deterministic noise-handling rule, not an agent-supplied lookup.

A sealed gate challenge must use an exact `(entity,action)` pair that was never observed in the 60 discovery records. Cells are ordered canonically by inferred group/action and entities by opaque ID. Exactly one held-out challenge is chosen from each of the first four eligible **distinct cells**. Fewer than four eligible distinct cells means immediate gate failure.

All four predictions are frozen before gate observation. The inherited `>=0.90` threshold on four observations requires `4/4` exact.

Thus A-gate success cannot be obtained by replaying an entity-specific observation. Each sealed prediction is transferred from other entities placed in the same inferred group.

## 2. Solution to the memorization problem

The model may output only a partition, never an A lookup or per-entity outcome parameters.

Binding representation constraints:

- 16 entities exactly;
- `2 <= k_hat <= floor(sqrt(16)) = 4`;
- every group used;
- at least two entities per group;
- every entity assigned exactly once.

The trivial `k_hat=16` lookup solution is structurally impossible.

Group labels are canonically relabeled by class membership before any scheduling, so integer label choice cannot manipulate which cells the Broker tests.

## 3. Exact B transfer construction

After A passes, the partition freezes permanently.

B has exactly 32 calibration and 32 sealed transfer observations.

For all inferred `(group,action)` cells in canonical order:

- first calibration pass places one sorted entity in every cell;
- extra passes add the next sorted entity only when doing so leaves at least one uncalibrated entity for that cell;
- stop exactly at 32 calibration observations.

This always succeeds for the legal geometry. One simple capacity argument is:

- base calibration count = `8*k_hat <= 32`;
- preserving one held-out entity per cell still permits up to `8*(16-k_hat)` calibration entity/action pairs, which is at least 96 for `k_hat<=4`.

The B lookup is deliberately stricter than the A noise reducer, per the prior referee ruling:

- all calibration outcomes identical -> cell defined;
- any disagreement -> cell inconsistent;
- every transfer relying on an inconsistent cell is forced incorrect;
- no majority vote or rescue.

Transfer slots are then filled in canonical rounds from entity/action pairs not used in calibration, until exactly 32 are frozen. Every transfer exact pair is unseen in B calibration.

## 4. A-only model compute

V1 removes all B-side model calls because no B theory is learned.

Full and Flat are therefore matched over the only phase in which representation learning occurs:

- Full: 6 Conjecturer + 6 Critic + 1 commit = 13 calls;
- Flat: 6 Generate + 6 same-role Select + 1 commit = 13 calls;
- maximum output-token envelope each = 40,960;
- no B LLM calls either arm.

The previously accepted realized-token audit is retained. A Full win with `R_compute>1.05` is invalidated; `R_compute<0.95` is reported as a conservative Flat compute advantage and does not invalidate a Full win.

## 5. Exact schemas and prompt drafts

The model-facing Theory AST is replaced by the minimal partition schema in `V1_SCHEMA_FREEZE.json`.

No program or formula field exists.

Prompt SHA-256 values:

- Conjecturer: `2b530b7f5328ae7080299adc00f90b4380cede58f2971400ba9eb5033b04fa4e`
- Critic: `545bd8213e567f1977ec4e15b6e2e5315056b5c0ccab6b01a60dc272b38b88c8`
- Flat: `b0bb11e6ff492fdacc4edc1d7fa852b595c1c6c9039872dd09e7dc77082ca412`

The V1 prompt drafts retain the previous semantic-nudge firewall and no-tool/no-history restrictions.

## 6. Null and primary analyses

Null positive remains intentionally early and strict:

> a committed partition passes the empirical A gate and advances to B.

100 Full Null worlds; 5+ positives triggers Hallucination Kill.

Causal primary endpoint remains world-level B transfer exact accuracy with zero for abstention/gate/schema/schedule failure.

100 paired causal worlds; one-sided paired sign-flip test; 100,000 draws; RNG seed `20260830`; alpha .05; minimum mean Full-over-Flat advantage .05. Both significance and effect floor are required.

## 7. One explicit noise consequence for referee review

Retaining the inherited 0.90 threshold on a four-observation A gate means the gate requires `4/4` exact. Even a perfect underlying partition is still exposed to the benchmark's 2% measurement corruption on each sealed challenge.

Under an idealized independent-noise approximation, the ceiling for a perfect four-prediction gate is approximately `0.98^4 ~= 0.922` before considering discovery-side noise. This affects both arms and preserves the old four-unit / 90% gate semantics, but it does introduce avoidable attrition.

I have **not** silently relaxed it. If the referee wants a noise-adjusted A gate, that must be ruled before implementation. The current freeze retains 4/4.

## 8. Requested rulings

### Ruling A — Empirical A gate

Accept, revise, or reject the exact A gate above: distinct-entity support >=2, strict-majority empirical cell prediction, four distinct held-out cells, and 4/4 sealed success.

### Ruling B — Cardinality/anti-memorization safeguard

Confirm that `2 <= k_hat <= floor(sqrt(16)) = 4`, minimum group size 2, no model-supplied lookup/program, and cross-entity A gate are sufficient to prevent the trivial lookup-table solution.

### Ruling C — Canonical B schedule

Confirm the exact 32-calibration / 32-transfer construction and forced-failure rule for inconsistent B cells.

### Ruling D — A-only compute schedule

Confirm removal of the now-useless four B research rounds and B commit from **both** arms, yielding matched 13-call / 40,960-output-token A-only envelopes.

### Ruling E — Implementation authorization

If A-D are accepted, authorize implementation of V1 Broker/schemas/orchestrators and independent synthetic tests only.

Do **not** authorize benchmark exposure yet. After implementation, CI, exact code hashes, provider adapter freeze, and execution guard are complete, return a final implementation checkpoint for separate benchmark authorization.
