# Archimedes V1 — B-Transfer CI Integrity Contract

**Status:** FROZEN BEFORE V1 BROKER IMPLEMENTATION

This document preregisters how automated CI will verify that the V1 Paradigm-B calibration and sealed-transfer schedule is deterministic, partition-conditioned only, outcome-blind at selection time, budget-exact, and free of hidden-world leakage.

The CI suite uses only independent hand-constructed partitions, deterministic fake runtimes, synthetic calibration outcomes, and exhaustive legal partition-size shapes. It must not import or instantiate causal or Null Archimedes benchmark worlds.

## 1. Pure scheduling boundary

The production schedule constructor must be a pure deterministic function of only:

- the canonical frozen inferred partition;
- the public entity identifiers `entity_00..entity_15`;
- the public action identifiers `0..7`;
- the fixed phase budgets `32` calibration and `32` transfer.

It must not accept, import, inspect, or branch on:

- ground-truth latent assignments;
- hidden A/B programs;
- benchmark/world seed;
- hidden calibration/transfer entity split from V0;
- calibration outcomes when selecting calibration interventions;
- transfer outcomes when selecting transfer interventions.

Calibration outcomes may be supplied only to the separate empirical lookup builder after the 32 calibration interventions are frozen and executed.

## 2. Canonicalization invariance test

For each synthetic partition fixture and for every permutation of its submitted class labels:

1. canonicalize classes by ascending minimum entity ID;
2. build the calibration schedule;
3. build the transfer schedule from the frozen calibration pairs;
4. serialize both schedules canonically;
5. compute SHA-256 digests.

CI requires every cosmetic relabeling of the same equivalence relation to produce byte-identical canonical partitions, calibration schedules, transfer schedules, and digests.

For `k=4`, all `4! = 24` label permutations are tested. The same complete permutation check is applied for `k=2` and `k=3`.

## 3. Input-order invariance test

The same partition is presented with entity-assignment mappings inserted in multiple different dictionary orders. CI requires identical canonical partition and schedule digests. No production ordering may depend on Python mapping/set iteration order.

## 4. Exhaustive legal group-size-shape test

CI enumerates every ordered integer composition of `16` into `k` parts for `k in {2,3,4}` with every part `>=2`.

For each legal size shape, a canonical synthetic partition is constructed from contiguous public entity IDs and the full B schedule is generated.

The following invariants must hold for every legal shape:

- exactly 32 unique calibration `(entity, action)` pairs;
- exactly 32 unique transfer `(entity, action)` pairs;
- calibration and transfer pair sets are disjoint;
- all selected entities belong to the schedule cell's canonical inferred group;
- all actions are in `0..7`;
- Pass 0 calibration contains exactly one observation for every canonical `(group, action)` cell;
- at least one uncalibrated entity/action pair remains in every cell after calibration;
- transfer allocation reaches exactly 32 slots without inventing or repeating a pair;
- total B observations are exactly `64`.

This is the mechanical proof that the frozen fill rule succeeds for every legal cardinality and every permitted group-size distribution, not merely a few example partitions.

## 5. Declarative reference-oracle test

The test suite contains a small, independent reference implementation of the frozen scheduling rules written for clarity rather than reuse of production helpers:

### Calibration oracle

1. enumerate cells `(q,a)` in lexicographic order;
2. Pass 0 selects member index `0` in every cell;
3. for `r = 1,2,...`, traverse cells lexicographically and select member `r` iff `r < group_size - 1`;
4. stop at exactly 32 selections.

### Transfer oracle

1. for every cell, compute sorted members whose exact `(entity,a)` pair was not calibrated;
2. for `r = 0,1,2,...`, traverse cells lexicographically and select remaining member `r` when present;
3. stop at exactly 32 selections.

For every exhaustive legal size shape and selected membership permutations, production output must equal the oracle slot-for-slot.

## 6. Outcome-blind schedule test

For a fixed canonical partition, CI supplies multiple radically different synthetic B calibration outcome tables, including:

- all zeros;
- all distinct/cycling values;
- deliberately inconsistent same-cell values;
- pseudorandom fixed synthetic values.

The calibration schedule and transfer `(entity, action, group)` schedule must remain byte-identical across all outcome tables.

Only the post-calibration prediction metadata may differ (`defined` versus `inconsistent`, and `predicted_y`).

## 7. Ground-truth blindness test

The scheduler is tested behind a narrow interface that contains no hidden-world object. CI additionally performs a static dependency check on the V1 scheduling module and fails if it references any of the following names or fields:

- `latent_q_by_entity`;
- `program_a`;
- `program_b`;
- `b_calibration_entities`;
- `b_transfer_entities`;
- benchmark generator helpers.

A synthetic fake object carrying those fields is also varied while the public partition is held fixed; schedule output must not change because those fields are not legal scheduler inputs.

## 8. Lookup consistency and forced-failure test

After the calibration schedule is frozen, CI constructs synthetic calibration outcomes and verifies the exact empirical lookup rule:

- one unique observed value in a cell -> `cell_status=defined` and that value is the prediction;
- two or more distinct values in the same cell -> `cell_status=inconsistent`;
- no majority vote, tie-break, smoothing, denoising, or model-selected rescue is permitted;
- every transfer record using an inconsistent cell has `predicted_y=null` and `forced_failure=true`;
- every such transfer slot is scored incorrect regardless of its sealed outcome.

A regression fixture explicitly uses a 2-to-1 apparent majority with one discordant value and still requires `inconsistent`, proving that no majority-vote logic has crept into B.

## 9. Freeze-before-observe ordering test

A deterministic fake runtime records every call. CI requires the Broker event order to be:

1. freeze canonical A partition;
2. construct/freeze 32 B calibration interventions;
3. execute exactly those 32 calibration observations;
4. construct the empirical B lookup;
5. construct all 32 transfer predictions and forced-failure flags;
6. compute and ledger the complete transfer-prediction digest;
7. only then invoke the runtime for the first sealed B-transfer outcome.

The fake runtime fails immediately if any B-transfer `observe()` occurs before the prediction-freeze ledger event.

No transfer outcome may influence any prediction or later transfer-pair selection.

## 10. Replay determinism test

For every core synthetic fixture, the complete B scheduling/prediction pipeline is run repeatedly in fresh objects/processes. CI requires equality of:

- canonical partition JSON;
- calibration schedule JSON;
- transfer schedule JSON;
- calibration schedule digest;
- transfer prediction digest;
- ordered cell statuses and predictions;
- final synthetic score for a fixed fake runtime.

No timestamp or process-local identifier may enter a scientific schedule digest.

## 11. Python hash-seed matrix

GitHub Actions runs the V1 deterministic-contract tests in separate processes under at least:

- `PYTHONHASHSEED=0`;
- `PYTHONHASHSEED=1`;
- `PYTHONHASHSEED=42`;
- `PYTHONHASHSEED=314159`.

The workflow compares emitted fixture digests against one committed expected digest manifest. A hash-seed-dependent schedule fails CI.

The scientific Python version is frozen separately in the V1 pre-exposure environment manifest; CI uses that exact version for the final freeze run.

## 12. Partition-membership metamorphic tests

For representative legal group-size shapes, CI deterministically permutes entity membership while preserving group sizes. For each transformed partition it verifies that:

- the schedule changes only as implied by the sorted public entity membership;
- no schedule slot refers to an entity outside its inferred group;
- the same canonical round rules are obeyed;
- the budget/disjointness/coverage invariants remain true.

This prevents an implementation from accidentally working only for contiguous or specially arranged groups.

## 13. Invalid-partition rejection tests

Before B scheduling, CI verifies immediate deterministic rejection of:

- `k_hat < 2`;
- `k_hat > 4`;
- missing entity assignment;
- duplicate/noncanonical entity identifier;
- unused declared group;
- group with fewer than two entities;
- assignment outside `0..k_hat-1`.

No invalid submission reaches the A empirical gate or B scheduler. In a scientific run it consumes the already-defined commit/gate path and closes that arm/world; there is no repair or relabeling that changes class membership.

## 14. Budget and ledger integrity tests

CI asserts exactly:

- 60 A discovery observations;
- 4 charged A-gate observations for a committed partition;
- 32 B calibration observations after A-gate success;
- 32 B transfer observations;
- total maximum scientific observation envelope `128`.

The B phase cannot request an extra observation to resolve an inconsistent or missing cell.

Ledger tests verify that schedule and prediction digests are recorded before sealed execution and that replay from the visible deterministic records reproduces the same digests.

## 15. CI release gate

Benchmark exposure must remain locked unless all of the following are true on the exact implementation commit proposed for freeze:

1. all ordinary unit tests pass;
2. exhaustive legal group-size-shape scheduling tests pass;
3. reference-oracle equality tests pass;
4. label/input-order invariance tests pass;
5. outcome-blindness and hidden-field firewall tests pass;
6. inconsistent-cell forced-failure tests pass;
7. freeze-before-observe tests pass;
8. hash-seed matrix produces the committed identical digest manifest;
9. the implementation commit/hash and V1 schema/prompt/config manifests are frozen;
10. the referee explicitly authorizes benchmark exposure after reviewing those artifacts.

CI success alone never authorizes benchmark execution.
