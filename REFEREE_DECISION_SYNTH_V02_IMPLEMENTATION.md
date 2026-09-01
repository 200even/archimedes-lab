# Referee Decision — EnumerativeSynthesizer V0.2 Implementation

**Decision:** AUTHORIZE V0.2 IMPLEMENTATION  
**Recorded:** 2026-08-31  
**Benchmark status:** No causal or Null Archimedes benchmark world has been exposed to any language model.

The referee authorized implementation of the preregistered bounded syntax-guided constraint synthesizer and exactly one execution on the frozen 1,000-AST qualification corpus.

Binding rulings:

1. The synthesizer may consume the LLM-committed latent cardinality and entity-to-latent assignments as fixed constants. It may not search, alter, merge, split, or compare alternative latent partitions.
2. A deterministic Z3 `rlimit` per synthesis invocation is mandatory. Wall-clock timeout is not the scientific resource limit.
3. The exact Z3 package version, solver parameters, and `rlimit` must be registered before qualification.
4. The frozen qualification corpus digest `e5a643f5b7bf4c9c69297108a9ad4fa29569ca52152de40a2449b98e9c998400`, grammar, depth limits, and 0.95 recovery threshold are immutable.
5. V0.2 receives exactly one qualification execution. If recovery is below 0.95, Tool-Assisted V0 is permanently abandoned. Individual failed corpus items may not be inspected for debugging.
6. Pre-qualification testing is restricted to independent synthetic fixtures and exhaustive small-depth grammar checks.
7. Benchmark execution remains prohibited.

This artifact records the manual referee ruling. It does not itself authorize benchmark exposure.
