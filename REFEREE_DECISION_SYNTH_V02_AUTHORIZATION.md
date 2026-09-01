# Referee Decision — Synthesizer V0.2 Authorization

**Decision:** AUTHORIZE SYNTHESIZER REVISION  
**Scope:** Exactly one benchmark-independent redesign of `EnumerativeSynthesizer V0.2`  
**Benchmark exposure:** PROHIBITED

The referee rejected accepting the V0.1 qualification result (82.6%) and rejected abandoning deterministic synthesis before one redesign attempt.

## Binding constraints

1. **One-shot rule.** Exactly one V0.2 redesign round is permitted. If V0.2 fails to reach 95% recovery on the frozen qualification corpus, Tool-Assisted V0 must be abandoned.
2. **Immutable grammar and corpus.** The 1,000-AST qualification corpus with SHA-256 beginning `e5a643f...`, the 95% recovery threshold, and the frozen public Theory AST grammar/depth limits may not change.
3. **No meta-overfitting.** V0.2 must be a general search improvement. No structural priors, heuristics, operator weightings, or hard-coded patterns may be derived from individual qualification failures.
4. **Architectural parity.** V0.2 must remain deterministic, may not search or modify latent partitions, and must be identically available to Full and Flat.
5. **Algorithmic preregistration.** The theoretical V0.2 algorithm must be submitted to the referee and approved before implementation or execution against the frozen qualification corpus.

No V0.2 implementation code may be written until the accompanying design checkpoint is authorized.
