# Archimedes — Referee Checkpoint: V1 Direct Entity-Transfer Design

**Status:** DESIGN PROPOSAL ONLY — NOT AUTHORIZED FOR IMPLEMENTATION OR BENCHMARK EXPOSURE

## Context

The referee has formally terminated Tool-Assisted V0. `EnumerativeSynthesizer V0.2` failed the required independent synthetic precondition and strict replay determinism requirement. The V0.2 1,000-AST qualification was never triggered, and no causal or Null Archimedes benchmark world has been exposed to a language model.

The failure is therefore localized to symbolic law compilation. The central D4 question remains untested:

> Can an epistemically scaffolded agent discover an unobserved reusable entity representation in Paradigm A, freeze it, and use it to predict interventions on previously unobserved entities under a structurally distinct Paradigm B better than a compute-matched Flat baseline?

This checkpoint proposes a successor protocol that removes symbolic program synthesis entirely rather than replacing it with another complex compiler.

## Proposed methodological change

### Replace symbolic-law synthesis with a deterministic empirical transfer table

After the agent freezes its A-discovered partition, the Broker treats the committed latent label for each entity as a fixed input. The deterministic evaluator never searches, modifies, merges, splits, or relabels the partition.

For Paradigm B, prediction uses only an empirical finite table:

`L_B(q_hat, a) -> y`

where:

- `q_hat` is the agent's frozen entity label from A;
- `a` is the intervention action in the public 3-bit action domain;
- `y` is the observed 3-bit outcome.

The table is not a learned symbolic theory and has no grammar. It is a deterministic lookup constructed from B calibration observations conditional on the agent's frozen partition.

If two calibration observations map to the same inferred cell `(q_hat, a)` but have different outcomes, that cell is marked **inconsistent** and cannot generate a successful transfer prediction. The evaluator does not resolve inconsistency by majority vote, smoothing, or optimization.

This eliminates symbolic regression as a source of false negatives. The only substantive learned object required for cross-entity transfer is the partition supplied by the language model.

## What D4 would mean in V1

V1 deliberately narrows the transfer claim to **zero-shot entity transfer after mechanism calibration**.

The agent first discovers and freezes an entity abstraction in A. It then receives bounded observations from structurally distinct B. Those observations establish B behavior for some representatives of the inferred classes. The sealed transfer test asks whether that same frozen abstraction correctly predicts B interventions on different entities that were not used to establish the corresponding lookup entries.

A successful transfer therefore demonstrates that the A-discovered labels identify an entity-level regularity that remains predictive when the causal mechanism changes.

V1 would **not** claim:

- discovery of a symbolic algebraic law;
- extrapolation to unseen `(q_hat, a)` combinations;
- minimality or recovery of the ground-truth cardinality unless separately measured;
- D5 ontology revision.

## Proposed observation accounting

Preserve the total 128-observation world envelope:

- 60 A discovery observations;
- 4 sealed A gate observations;
- 32 B calibration observations, reusing the former `28 B calibration + 4 B-theory-evaluation` budget as one calibration phase;
- 32 sealed B transfer observations.

No additional observations are introduced.

## B calibration and sealed-transfer pairing

The core transfer unit is a matched latent-cell pair.

For an inferred class `q_hat` and action `a`:

1. a B calibration observation is obtained on entity `e_cal` assigned to `q_hat`;
2. a sealed B transfer intervention uses the same action `a` on a distinct entity `e_test != e_cal` that the frozen partition also assigns to `q_hat`;
3. the predicted transfer outcome is the calibration lookup value `L_B(q_hat,a)`;
4. the trusted evaluator compares that prediction with the sealed outcome of `e_test`.

Because every inferred class must contain at least two entities under the existing cardinality safeguards, distinct calibration and transfer representatives are structurally available.

### Deterministic construction proposal

After the A partition is frozen, the Broker constructs calibration/transfer pairs using only the committed partition and public entity/action identifiers:

- classes ordered by numeric frozen label;
- entities within each class ordered by opaque entity ID;
- actions ordered `0..7`;
- for each class/action cell, choose the first entity in the class as calibration representative and the second entity as transfer representative;
- continue in canonical `(q_hat,a)` order until the fixed budget is filled;
- if fewer than 32 distinct class/action cells exist because `k_hat < 4`, use subsequent entities in the same class as additional transfer representatives in canonical order; no calibration cell is invented or extrapolated;
- a transfer prediction counts as valid only when its calibration lookup cell is defined and internally consistent.

The exact fill rule for `k_hat < 4` should be frozen before implementation if the referee accepts the architecture.

## Why this isolates the concept variable

The deterministic table cannot invent a latent representation. It receives the partition as constants.

It also cannot perform algebraic search. Once a calibration cell is observed, its prediction for a same-cell held-out entity is mechanically determined.

Thus a transfer error can be attributed much more directly:

- if the inferred partition groups entities that truly share the reusable hidden entity factor, calibration values transfer to other members;
- if the inferred partition groups causally different entities, same-cell calibration observations become inconsistent or fail on held-out entities.

This makes the D4 test closer to a direct measurement of representation quality than Tool-Assisted V0 was.

## Full vs Flat parity

Retain the referee-accepted compute-matched language-model schedule unless separately amended:

- Full: 12 Conjecturer calls + 10 Critic calls = 22 total;
- Flat: 10 Generate + 10 same-role Select + 2 Commit = 22 total;
- prospective maximum output envelope: 69,632 tokens per completed world for each arm;
- aggregate realized provider-token audit retained;
- a Full win is invalid if `R_compute = Full / Flat > 1.05`;
- `R_compute < 0.95` is conservative for a Full win and does not invalidate it.

The deterministic transfer table is identical code for both arms and performs no search, so solver-operation parity is no longer a scientific issue.

## Benchmark firewall

No benchmark execution is requested by this checkpoint.

Before any language model sees a causal or Null world, V1 would require a new pre-exposure freeze covering:

- exact B pair-construction rule;
- exact handling of inconsistent calibration cells;
- exact scoring of missing/invalid transfer cells;
- exact A-gate semantics without symbolic AST synthesis;
- exact Null positive-declaration rule under the new representation;
- exact prompt schemas if the removal of program AST output changes the agent interface;
- model/version and provider metadata;
- Full/Flat parity;
- cross-world analysis and kill criteria.

## Proposed primary V1 outcome

For each world, score the fraction of 32 sealed B entity-transfer interventions predicted exactly by the frozen A representation plus deterministic B lookup. Invalid, missing, inconsistent, abstained, or non-transfer-qualified worlds score `0.0`, preserving the conservative world-level analysis principle.

The preregistered paired Full-vs-Flat cross-world test can remain the one-sided paired sign-flip analysis with the existing minimum mean advantage, subject to referee approval.

## Null worlds

The existing Null principle remains important. In a pure-noise world, arbitrary entity partitions should not support stable same-cell held-out transfer. The exact declaration/FPR rule must be re-frozen for V1 before exposure.

## Scientific interpretation if V1 succeeds

A defensible claim would be:

> Within a preregistered finite representational geometry, an epistemically scaffolded AI system discovered an entity-level latent abstraction in one causal paradigm that, after bounded calibration to a structurally distinct mechanism, supported zero-shot prediction on held-out entities better than a compute-matched flat model.

This is narrower than symbolic scientific-law discovery, but it directly tests reusable concept formation without an unreliable algebraic compiler in the causal chain.

## Requested referee rulings

### Ruling A — Is this a valid successor D4 test?

Does replacing symbolic law synthesis with deterministic same-cell held-out entity transfer preserve a scientifically meaningful D4 concept-discovery claim, provided the claim is explicitly narrowed to zero-shot entity transfer after B calibration?

### Ruling B — May the former 28+4 B budget be unified?

May the frozen total observation envelope be preserved by treating the former `28 B calibration + 4 B-theory evaluation` observations as a single 32-observation B calibration budget, given that there is no longer a symbolic B theory gate?

### Ruling C — Is the deterministic partition-conditioned pair construction acceptable?

Does constructing calibration/transfer pairs deterministically from the agent's already-frozen partition improperly privilege the proposed representation, or is it an appropriate direct test of whether that representation predicts held-out entities?

If partition-conditioned scheduling is considered too endogenous, please require an alternative schedule before implementation.

## Authorization requested

If A/B/C are accepted, authorize **design completion only** for V1: exact schemas, pair-construction algorithm, scoring rules, and new pre-exposure freeze. Do not authorize causal/Null benchmark execution yet.
