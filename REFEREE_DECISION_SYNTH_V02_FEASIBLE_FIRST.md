# Referee Decision — Final V0.2 Feasible-First Correction

**Decision:** AUTHORIZE ONE FINAL SEMANTICS-PRESERVING ENGINEERING CORRECTION

The referee authorized exactly one final algorithmic adjustment before the one-shot V0.2 qualification: replace lower-bound-first SMT optimization with a deterministic feasible-incumbent-first anytime schedule.

Binding conditions:

- Before code changes, preregister the exact deterministic feasible-first schedule.
- No target-specific operator ordering, structural templates, or grammar weighting may be introduced.
- The frozen 1,000-AST qualification corpus and digest remain unchanged.
- Qualification recovery threshold remains 0.95.
- The cumulative Z3 `rlimit` remains 50,000,000 per search invocation.
- After synthetic fixtures pass and the implementation is frozen, execute the qualification exactly once.
- Benchmark execution remains prohibited.

This decision authorizes search-order changes only. The Theory AST grammar, hypothesis class, latent-partition firewall, objective hierarchy, solver package/version, and scientific benchmark remain unchanged.
