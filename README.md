# Archimedes V0 — Hidden World Generator

This repository contains the first authorized implementation artifact for **Archimedes**, an experiment in autonomous explanatory concept discovery. V0 deliberately contains **no Conjecturer prompt**. The preregistration freeze is committed before any Conjecturer implementation.

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

## Experimental status

**Referee decision: C — AUTHORIZE V0 ONLY.**

V0 tests D4 only: frozen latent identity reused across a structurally distinct paradigm and evaluated through sealed interventional transfer. D5 ontological revision is explicitly deferred.

See [`PRE_REGISTRATION_FREEZE.md`](PRE_REGISTRATION_FREEZE.md) for the binding V0 execution contract.
