# Archimedes V0 — Pre-Code Freeze

**Freeze version:** 0.1.2  
**Status:** Binding for V0 before any Conjecturer prompt is written.

## Primary V0 claim

Archimedes-Full will be tested for improvement over Flat LLM + symbolic/program synthesis on **D4 frozen-value cross-paradigm interventional transfer**, while maintaining Null-World concept false-positive rate below 0.05.

D5 is deferred and may not be claimed from V0.

## Hidden-world meta-grammar

The V0 domain is the finite opaque alphabet `D = {0,...,7}`. No spatial, temporal-dynamical, mechanical, geometric, energetic, electrical, biological, or other physical semantics are exposed.

Each causal world contains 16 opaque entities. The hidden entity variable `q ∈ D` occurs exactly twice for each value, randomly assigned to entity identifiers.

Allowed hidden program templates are frozen as:

### Paradigm A: modular arithmetic family

`A1(q,x) = P_A((q + (2q+1)*(a*x + c1) + c2) mod 8)`

`A2(q,x) = P_A((q + a*x + c1) mod 8)`

where `a ∈ {1,3,5,7}`, `c1,c2 ∈ D`, and `P_A` is a uniformly shuffled permutation of D.

### Paradigm B: bitwise family

`B1(q,u) = P_B(rotl3(q,r) XOR rotl3(u,s))`

`B2(q,u) = P_B(rotl3(q XOR c1,r) XOR (u XOR c2))`

where `r,s ∈ {1,2}`, `c1,c2 ∈ D`, and `P_B` is a uniformly shuffled permutation of D.

Maximum expression depth is **6**. No other hidden operators or templates may be added during V0 without declaring a new preregistration version and invalidating comparison with frozen V0 results.

The overlap of A and B is limited to opaque inputs/outputs, q, and final random permutation. A's discriminating operator family is modular arithmetic; B's is bitwise XOR/rotation.

## Solvability gate

A generated causal world is admitted only if all of the following are true before agent exposure:

1. q appears exactly twice for each of the 8 states.
2. Full-action response signatures uniquely distinguish every q state in A.
3. Full-action response signatures uniquely distinguish every q state in B.
4. For every q, each paradigm produces at least 4 distinct outputs over legal actions.
5. For every action, varying q produces at least 4 distinct outputs.
6. Constant predictor accuracy is ≤ 0.50.
7. Action-only mode predictor accuracy is ≤ 0.75.
8. Entity-only mode predictor accuracy is ≤ 0.75.
9. The B calibration/transfer split contains exactly one representative of each hidden q state on each side.

## Measurement model

The observable `y` lies in D. Causal-world measurements are independently corrupted at a known rate of **0.02**. A corrupted observation is replaced with a uniformly selected different value in D. Measurement replay is deterministic for the tuple `(world, paradigm, entity, action, repetition)` so an audit can exactly reproduce the ledger.

Null Worlds ignore intervention and entity state and return deterministic-replay pseudorandom values uniformly over D. They contain no hidden q or causal program.

## JSON schemas

The exact Theory AST and Experiment AST schemas are generated from `archimedes_v0.ast_schema` into `schemas/theory_ast.schema.json` and `schemas/experiment_ast.schema.json`. Unknown fields are forbidden. Neither schema contains a free-form rhetorical-justification field or chain-of-thought field.

## Stable identity tolerance

q is discrete. After the end of Paradigm A, the Broker freezes the latent assignments used by the candidate D4 theory. **Zero assignment changes are permitted** during B calibration or B transfer evaluation.

This is the V0 interpretation of `q_hat^(A) ≈ q_hat^(B)`: the tolerance is exactly zero edits to the frozen assignments. Numeric label names are not assumed to equal the generator's private q labels; D4 is judged by predictive transfer, not by semantic label matching.

## Broker budget

Exactly **128 interventions per world** on a D4 claim path:

- 64 A-discovery interventions.
- 32 B-calibration interventions.
- 32 sealed B-transfer evaluation interventions.

The transfer-evaluation responses are not returned to the operating agent until the world's run is closed. A condition-blind `no_concept` abstention after the 64 A interventions closes the run and forfeits the unused B budget, as specified in amendment 0.1.2 below.

Maximum epistemic cycles: **12**.

## Individual-world D4 qualification

A candidate D4 concept must:

1. be frozen after Paradigm A;
2. undergo zero latent-assignment edits thereafter;
3. be used during B calibration as-is;
4. achieve at least **0.90 exact predictive accuracy** on the 32 sealed B-transfer measurements.

This per-world threshold is not itself the primary statistical claim. The primary test is the preregistered cross-world comparison of Archimedes-Full versus Flat LLM + synthesis on sealed D4 transfer performance.

## Binding kill criteria

1. **Hallucination Kill:** high-confidence concept FPR on Null Worlds ≥ 0.05.
2. **Critic Kill:** during critic qualification, failure to find a falsifying intervention for deliberately injected structurally flawed theories in 3 consecutive eligible cycles.
3. **Baseline Kill:** no statistically significant Archimedes-Full improvement over Flat LLM + synthesis on D4 zero-shot/frozen-identity interventional transfer.

The exact cross-world statistical test, sample size, and high-confidence declaration threshold must be frozen before running the first comparative model experiment. They are intentionally not chosen by the world generator.

## Causal isolation protocol

Conjecturer and Critic are stateless inference calls with no shared session or hidden conversational state.

The Conjecturer may receive only the permitted observation ledger, normalized current Theory ASTs, and deterministic scores. Its raw prose and hidden reasoning are never passed to the Critic.

The Broker validates the Conjecturer output against the frozen Theory AST schema and strips/rejects any invalid payload.

The Critic receives only: (a) immutable permitted observation records, (b) neutralized Theory AST(s), (c) legal Experiment AST schema, and (d) remaining intervention budget. It does not receive the Conjecturer prompt, raw response, rhetorical justification, confidence language, or conversation history.

The Critic's raw prose and hidden reasoning are never passed back to the Conjecturer. Only schema-valid Experiment ASTs and deterministic adjudication results enter the shared ledger.

No agent-side process may mount, import, inspect, or query the hidden world file, generator source, generation seed, validation report, ground-truth q, hidden program parameters, or B transfer results before run closure.

## Pre-agent blinding amendment (0.1.1)

Added before any Conjecturer prompt or model experiment. This amendment changes no causal grammar, threshold, budget, metric, or hypothesis. It closes a metadata leakage route discovered during Broker implementation.

Agent-visible world metadata must not reveal either the generator seed or whether a world is causal versus Null. Accordingly:

- public `world_kind` is always the condition-neutral value `experimental`;
- benchmark bundles receive opaque random `world_id` values unrelated to seed or condition;
- the raw generator seed and true `world_kind` remain trusted-side only;
- filenames exposed to an agent may not encode `null`, `causal`, or the seed.

This is a blinding safeguard, not an experimental degree of freedom. The hidden artifact retains the seed and condition for evaluator replay after unblinding.

## Pre-agent theory-grounding and abstention amendment (0.1.2)

Added before any Conjecturer prompt or comparative model run. This amendment closes construct-validity routes discovered during Broker audit; it does not change the Hidden World grammar, intervention counts on a D4 claim path, transfer threshold, or primary hypothesis.

1. **Theory-grounded transfer.** A D4 claim must be generated by the committed Theory AST itself. After B calibration, the Broker deterministically evaluates the frozen B program with the frozen latent assignments to commit all 32 transfer predictions *before* requesting any sealed B-transfer measurements. The operating agent cannot submit independent transfer guesses that bypass its stated explanatory concept.
2. **Visible explanatory fit.** The A theory must fit the 64 A-discovery observations at **>= 0.90 exact accuracy**, and the final B program must fit the 32 visible B-calibration observations at **>= 0.90 exact accuracy**. These are construct-validity gates, not the primary comparative endpoint.
3. **Operator diversity.** The nontrivial operator signatures of the committed A and B programs must be nonempty and disjoint. Final categorical permutation wrappers do not count toward operator diversity.
4. **Complexity bound.** Submitted explanatory programs may not exceed the already frozen maximum expression depth of **6**.
5. **Condition-blind abstention.** After exactly 64 A interventions, the agent may irreversibly declare `no_concept`. This path is available identically in causal and Null worlds. It closes the run and forfeits the unused B budget. On a causal world it counts as D4 failure; on a Null world it is the intended true-negative behavior. Thus the Null false-positive test does not force an agent to hallucinate a latent concept merely to advance the Broker state machine.

For the Null-World kill criterion, a **concept declaration** is operationally defined as a Broker-accepted A theory that clears the >=0.90 visible-fit gate and advances to B calibration. Rejected candidate theories and `no_concept` abstentions are not positive concept declarations.
