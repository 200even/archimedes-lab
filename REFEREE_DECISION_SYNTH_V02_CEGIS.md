# Referee Decision — V0.2 CEGIS Supplement

**Decision:** AUTHORIZE CEGIS SUPPLEMENT

The deterministic counterexample-guided inductive synthesis (CEGIS) supplement is authorized as the final architecture for `EnumerativeSynthesizer V0.2`.

## Binding interpretation

CEGIS preserves the frozen hypothesis class. The entity-to-latent partition remains an immutable input to synthesis and is never searched, split, merged, or mutated by the solver. The trusted deterministic evaluator verifies every SAT candidate against the complete visible observation set.

The working set is deterministic and monotonic:

- initialize with the first canonical observation;
- on failure, append exactly the first canonical violating observation not already present;
- use no stochastic selection, heuristic counterexample scoring, tunable batch size, or restart policy.

All Z3 calls share the single cumulative deterministic resource budget already frozen for V0.2:

- `z3-solver==5.1.0.0`;
- `z3.Solver`;
- `auto_config=true`;
- `random_seed=0`;
- `timeout=0`;
- cumulative `rlimit=50,000,000` per synthesis invocation.

Rebuilding a solver never resets the scientific resource budget. If the CEGIS process exhausts that cumulative budget before finding a full-observation-valid candidate, the synthesis invocation fails.

## Authorization sequence

1. Implement the CEGIS loop.
2. Test only on independent synthetic fixtures and exhaustive small-depth grammar checks.
3. Freeze the final implementation hash.
4. Create `V02_QUALIFICATION_TRIGGER.txt` exactly once.
5. Execute the frozen 1,000-AST qualification corpus exactly once.
6. Read only aggregate qualification output.

If the aggregate recovery rate is below `0.95`, Tool-Assisted V0 is permanently abandoned. There will be no V0.3 synthesizer.

**Benchmark execution remains prohibited.**
