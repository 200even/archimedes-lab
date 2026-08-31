# Archimedes V0 — Hidden World Generator

This package is the first authorized implementation artifact for Archimedes V0. It deliberately contains **no Conjecturer prompt**. The preregistration freeze is committed before any Conjecturer implementation.

## Boundary

The generator produces two artifacts per world:

- `*.public.json` — safe for the Broker/agent side.
- `*.hidden.json` — sealed ground truth. Never mount or expose this file in the agent process.
- `*.validation.json` — generator-side solvability/nontriviality report. Keep sealed during a run because it contains structural diagnostics.

The runtime in `world.py` should execute in a process/container inaccessible to the agent. The Broker should expose only legal interventions and returned measurements.

## V0 concept structure

Each causal world has 16 opaque entities and an unobserved categorical quantity `q ∈ {0..7}`. Every q state occurs on exactly two entities. Paradigm A and B use q in structurally different operator families:

- A: modular arithmetic + a random permutation.
- B: bitwise transformations + a random permutation.

The B split is stratified but hidden: one member of each q pair is available for B calibration and the other is sealed for transfer. A representation that merely memorizes entity IDs cannot transfer; a stable grouping learned in A can.

## Run

```bash
python -m archimedes_v0.cli 42 --out worlds
python -m archimedes_v0.cli 43 --out worlds --null
pytest -q
```

## Non-claim

V0 does not test D5 ontological revision. It tests D4 only: frozen latent identity reused across a structurally distinct paradigm and evaluated through sealed interventional transfer.

## Experiment Broker

`archimedes_v0.broker.ExperimentBroker` now enforces the V0 execution boundary before any Conjecturer exists:

- exactly 64 visible A-discovery interventions before theory freeze;
- immutable freezing of the entity-level latent assignments;
- exactly 32 visible B-calibration interventions on the broker-revealed calibration subset;
- deterministic generation of 32 sealed B-transfer challenges (four distinct actions for each held-out entity);
- no transfer measurement is returned to the operating agent before run closure;
- exact 128-intervention exhaustion before D4 scoring;
- a hash-chained append-only experiment ledger; and
- the preregistered 12-cycle epistemic cap.

The trusted runtime key used to select transfer challenges stays behind the Broker boundary. The agent can inspect the challenge interventions once B transfer begins, but cannot derive them from repository source alone and never receives their outcomes until the run is closed.

### Condition blinding

A pre-agent audit found that early development IDs encoded the seed and causal/Null condition. That would invalidate the Null-World false-positive test. V0.1.1 closes this route: benchmark bundles use opaque random world IDs and expose the same public `world_kind: experimental` for causal and Null worlds. Seed and true condition remain sealed evaluator metadata only. See the blinding amendment in `PRE_REGISTRATION_FREEZE.md`.

### Theory-grounded D4 scoring

V0.1.2 adds a deterministic theory evaluator between the model and the transfer score. A and B explanatory programs must clear the frozen 0.90 visible-fit gates, obey the depth-6 complexity bound, and use disjoint nontrivial operator signatures. The Broker then derives all 32 sealed transfer predictions directly from the committed Theory AST and frozen latent assignments; an agent cannot bypass its stated theory by submitting ad hoc transfer guesses.

The Broker also exposes a condition-blind `declare_no_concept()` path after the 64 A interventions. This is necessary for a meaningful Null-World false-positive test: abstention is allowed in every world, closes the run irreversibly, and forfeits the remaining budget.
