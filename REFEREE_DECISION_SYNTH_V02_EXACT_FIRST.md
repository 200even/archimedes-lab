# Referee Decision — V0.2 Phase-1 Exact-First Clarification

**Decision:** A — CLARIFY / AUTHORIZE PHASE-1 EXACT-FIRST ORDER

The referee authorized one final clarification of the already-authorized feasible-first search schedule before the one-shot qualification.

Binding sequence:

1. **Fallback:** first establish any full-`O`-verified legal incumbent under maximally permissive legal bounds.
2. **Exact-first:** immediately query the mathematical Hamming lower bound `E <= 0`, with no node-count or depth minimization constraints beyond the frozen maximum grammar skeleton.
3. **Binary tightening of the remaining Hamming interval:** only if `E <= 0` is proven infeasible, search the remaining integer Hamming interval deterministically.
4. **Structural tightening:** only after the minimum Hamming error is established, minimize active nodes, then depth, then apply the frozen canonical AST tie-break.

Additional binding conditions:

- The `E <= 0` query must not include structural minimization.
- No target-specific operator ordering, structural template, grammar weighting, restart, alternate solver, or other heuristic may be introduced.
- The frozen 1,000-AST corpus, corpus digest, 95% threshold, grammar, Z3 package/configuration, and cumulative `rlimit=50,000,000` remain unchanged.
- After the independent synthetic suite passes, freeze the implementation hash and execute the frozen 1,000-AST qualification exactly once.
- Recovery below 95% terminates Tool-Assisted V0; there is no V0.3.
- Causal and Null Archimedes benchmark execution remains prohibited.

This decision was supplied by the external referee before the schedule amendment or exact-first code change.