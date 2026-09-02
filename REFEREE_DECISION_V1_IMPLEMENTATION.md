# Referee Decision — V1 Implementation Authorization

**Decision:** AUTHORIZE V1 IMPLEMENTATION (NO BENCHMARK EXPOSURE)

## Accepted rulings

The referee accepted the following V1 design elements:

1. **Empirical A-Gate:** cross-entity empirical prediction is the required defense against entity-specific lookup memorization.
2. **Cardinality safeguard:** enforce `2 <= k_hat <= 4` for 16 entities, with at least two entities in every declared class.
3. **Canonical B schedule:** deterministic partition-conditioned B calibration/transfer construction is accepted, including automatic forced failure for inconsistent B cells.
4. **A-only compute parity:** remove all B-side language-model calls; Full and Flat remain prospectively matched at 13 calls and 40,960 maximum output tokens through A commit.
5. **A-gate threshold:** retain the inherited `>= 0.90` semantic threshold. With four sealed A-gate predictions this means exactly 4/4 correct; the resulting measurement-noise attrition is accepted and must not be relaxed.

## Authorization boundary

Authorized:

- implement the V1 Broker;
- implement V1 schemas;
- implement V1 Full/Flat orchestrators;
- implement deterministic A-gate and B calibration/transfer schedule exactly as frozen;
- test only on independent synthetic fixtures and deterministic fake runtimes;
- add CI checks for schedule determinism, canonicalization, budget integrity, leakage firewalls, and freeze-before-observe ordering.

Still prohibited:

- supplying any causal Archimedes benchmark world to a language model;
- supplying any Null Archimedes benchmark world to a language model;
- tuning prompts, schedules, thresholds, or algorithms against benchmark outcomes;
- changing the 4/4 A-gate requirement without a new referee ruling.

## Required pre-exposure condition

Before any benchmark unlock, CI must demonstrate the deterministic integrity of the V1 B-transfer construction under the frozen public geometry and all legal partition cardinalities. The companion preregistration is `V1_B_TRANSFER_CI_INTEGRITY_SPEC.md`.
