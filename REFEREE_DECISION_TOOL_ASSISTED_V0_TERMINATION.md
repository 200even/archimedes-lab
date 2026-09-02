# Referee Decision — Terminate Tool-Assisted V0

**Decision:** A. TERMINATE TOOL-ASSISTED V0

**Status:** BINDING

## Ruling

Tool-Assisted V0 is formally abandoned. The deterministic synthesis tool is disqualified for the required Theory AST grammar under the frozen solver and resource constraints.

The binding reasons are:

1. The independent synthetic precondition did not pass. In particular, the final authorized V0.2 implementation failed to recover the legal depth-4 nested-permutation fixture within the frozen `rlimit=50,000,000` envelope.
2. Mechanical replay was not reproducible at the SAT-check-count level (`12` vs `13` on identical replay), violating the strict deterministic-compute-parity requirement imposed for the shared compiler.
3. The redesign budget is exhausted. No V0.3, further solver rewrite, additional equivalence-class engineering, or qualification run is permitted under Tool-Assisted V0.
4. The one-shot V0.2 qualification trigger was never created. The frozen 1,000-AST V0.2 qualification corpus was therefore never executed by the V0.2 synthesizer.
5. No causal or Null Archimedes benchmark world has been exposed to a language model. The D4 scientific hypothesis remains untested by this failure.

## Interpretation boundary

This is an engineering disqualification of the algebraic compiler, not evidence for or against the Archimedes D4 epistemic hypothesis.

The referee's rationale includes the expectation that the failed synthetic precondition makes the 95% qualification target implausible under the frozen architecture. For scientific precision, this repository records the actual binding empirical conclusion as **failure of the preregistered synthetic precondition and determinism requirement**, not as a mathematical proof that qualification success had literally zero probability.

## Prohibitions now in force

- Do not create `V02_QUALIFICATION_TRIGGER.txt`.
- Do not execute the V0.2 1,000-AST qualification run.
- Do not make further algorithmic changes to `EnumerativeSynthesizer V0.2` in an attempt to revive Tool-Assisted V0.
- Do not expose causal or Null benchmark worlds without a separately preregistered and referee-authorized successor protocol.

## Preserved scientific assets

The following remain scientifically usable because benchmark exposure did not occur:

- sealed causal and Null world generators;
- preregistered observation budgets and rejection-sampling firewall;
- A/B non-isomorphism checks;
- latent-cardinality and representation-freeze rules;
- Conjecturer/Critic causal isolation;
- compute-matched Full vs Flat call schedule;
- aggregate realized-token validity rule;
- cross-world paired analysis plan;
- Null false-positive kill criterion.

A successor experiment must explicitly separate itself from Tool-Assisted V0 and obtain referee approval before any benchmark exposure.
