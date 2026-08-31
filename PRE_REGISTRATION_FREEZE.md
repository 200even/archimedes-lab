# Archimedes V0 — Pre-Code Freeze

**Freeze version:** 0.1.3  
**Status:** HOLD — revised safeguards implemented for referee evaluation; no Conjecturer prompt may be written until referee authorization.

## Primary V0 claim

Archimedes-Full will be tested for improvement over Flat LLM + symbolic/program synthesis on **D4 frozen-value cross-paradigm interventional transfer**, while maintaining Null-World concept false-positive rate below 0.05.

D5 ontological revision is deferred and may not be claimed from V0.

## Referee-triggered V0.1.3 changes

V0.1.3 implements the three mandatory revisions from the HOLD ruling:

1. **Latent-cardinality anti-memorization:** hidden/inferred `k` with hard cap `k_max = floor(sqrt(|E|)) = 4`, plus minimum reuse of two entities per state.
2. **Economic visible-fit gates:** theory evaluation consumes the same frozen 128-unit resource budget as interventions, and each A/B fit gate may be attempted exactly once. Failed or malformed theories close the world irreversibly.
3. **SMT non-isomorphism adjudication:** Z3 checks whether A and B truth tables are equivalent under arbitrary bijective relabelings of latent states, intervention symbols, and output symbols. D4 is rejected when such an isomorphism exists.

These revisions were implemented before any Conjecturer/Critic prompt or model experiment.

---

## Hidden-world meta-grammar

The observable/intervention alphabet remains the finite opaque domain:

`D = {0,...,7}`.

No spatial, temporal-dynamical, mechanical, geometric, energetic, electrical, biological, or other physical semantics are exposed.

Each causal world contains 16 opaque entities. The hidden reusable quantity `q` has a cardinality sampled from:

`k_true ∈ {2,3,4}`.

The true value of `k` is trusted-side metadata only and must never appear in the agent-visible world descriptor, filename, ID, ledger projection, or prompt.

Entity assignments are near-balanced: every hidden state occurs at least twice and state counts differ by at most one.

### Paradigm A hidden family

`A1(q,x) = P_A((q + (2q+1)*(a*x + c1) + c2) mod 8)`

`A2(q,x) = P_A((q + a*x + c1) mod 8)`

where `a ∈ {1,3,5,7}`, `c1,c2 ∈ D`, and `P_A` is a uniformly shuffled permutation of D.

### Paradigm B hidden family

`B1(q,u) = P_B(rotl3(q,r) XOR rotl3(u,s))`

`B2(q,u) = P_B(rotl3(q XOR c1,r) XOR (u XOR c2))`

where `r,s ∈ {1,2}`, `c1,c2 ∈ D`, and `P_B` is a uniformly shuffled permutation of D.

Maximum Theory AST expression depth is **6**.

No hidden template may be added to V0.1.3 without a new preregistration version.

---

## A2 latent-cardinality rule

The candidate theory is not told the true latent cardinality. It may propose one finite-discrete entity-level latent variable with:

`2 <= k_hat <= floor(sqrt(16)) = 4`.

This is the referee-approved hard-limit alternative to full Minimum Description Length optimization.

The schema additionally requires:

- every declared state `0..k_hat-1` is used;
- each state is assigned to at least two entities;
- all 16 entities receive exactly one assignment;
- the latent domain is frozen as `finite_discrete`;
- the latent geometry is frozen as `unsigned_bitvector3`.

Therefore a one-state-per-entity lookup table (`k = |E| = 16`) is schema-invalid and cannot reach a theory gate.

The value of `k_hat`, domain kind, geometry, and every entity assignment are frozen with the accepted A theory. **Zero edits** to any of them are permitted after Paradigm A.

V0 does not permit arbitrary scalar/vector/relational latent structures. That remains a D5 question.

---

## B2 hypothesis-language rule

The Theory AST includes the true finite-domain operator vocabulary plus same-type distractors.

True-generator-capable primitives:

- `add_mod`
- `mul_mod`
- `xor`
- `rotl`
- `permute`

Preregistered distractor primitives:

- `bit_and`
- `bit_or`
- `min_u3`
- `max_u3`
- `abs_diff`
- `eq_mask`

All primitives operate only on the same 3-bit finite domain. The distractors do not reveal themselves through foreign types such as floats, strings, trigonometric functions, or continuous geometry.

The hidden-world generator is unchanged by the distractor DSL: it never samples the distractor operators.

---

## Hidden-world admission / solvability gate

A generated causal world is admitted only if all of the following hold before agent exposure:

1. `k_true ∈ {2,3,4}`.
2. Every true latent state is represented, with at least two entities per state and near-balanced counts.
3. Full-action response signatures uniquely distinguish every true latent state in A.
4. Full-action response signatures uniquely distinguish every true latent state in B.
5. For every q, each paradigm produces at least four distinct outputs over legal interventions.
6. For every intervention, varying q produces at least `min(4,k_true)` distinct outputs.
7. Constant predictor accuracy is <= 0.50.
8. Action-only mode predictor accuracy is <= 0.75.
9. Entity-only mode predictor accuracy is <= 0.75.
10. The B calibration/transfer split is exactly 8/8 and every true latent state appears on both sides.
11. The hidden A/B interaction families are distinct.
12. The Z3 finite-isomorphism query returns **UNSAT** for the hidden A/B truth tables under arbitrary latent/action/output relabelings.

Worlds failing any criterion are rejected before Archimedes can see them.

---

## SMT / Z3 structural non-isomorphism

For an accepted candidate D4 theory, define finite truth tables:

`T_A(q,x)` and `T_B(q,u)`

for all candidate latent states `q ∈ {0,...,k_hat-1}` and all eight legal intervention values.

The deterministic adjudicator asks whether there exist bijections:

- `phi_q` over latent-state labels,
- `phi_a` over intervention symbols,
- `phi_y` over output symbols,

such that for every q and intervention a:

`phi_y(T_A(q,a)) = T_B(phi_q(q), phi_a(a))`.

The bijections and universal finite constraints are encoded in Z3.

- `SAT` means the two paradigms are structurally isomorphic under opaque relabeling and **D4 is rejected**.
- `UNSAT` is required to proceed to sealed transfer.

The adjudicator also retains the simpler requirement that the nontrivial operator signatures of A and B are nonempty and disjoint. The SMT criterion is the stronger protection against algebraic disguises.

The Z3 result and SHA-256 digests of both finite truth tables are written to the trusted ledger for audit.

---

## Measurement model

Observable `y` lies in D. Causal-world measurements are independently corrupted at a known rate of **0.02**. A corrupted observation is replaced with a uniformly selected different value in D.

Measurement replay is deterministic for `(world, paradigm, entity, action, repetition)` so an audit can reproduce the ledger.

Null Worlds ignore entity/intervention structure and return deterministic-replay pseudorandom values uniformly over D. They contain no hidden latent cardinality, q assignments, or causal program.

---

## V0.1.3 resource budget and rejection-sampling firewall

The total resource budget on a completed D4 path remains exactly **128 units**, but visible-fit evaluation is no longer free:

- **60** A-discovery interventions
- **4** units for the single A-theory gate evaluation
- **28** B-calibration interventions
- **4** units for the single B-theory gate evaluation
- **32** sealed B-transfer interventions

Total:

`60 + 4 + 28 + 4 + 32 = 128`.

### Gate rule

Each visible-fit gate has **exactly one attempt**.

The gate charge is consumed **before** schema parsing, structural validation, or fit scoring. Therefore malformed, low-fit, or otherwise invalid theories still consume the gate allocation.

If the A theory fails its gate, the world closes immediately as an A gate failure.

If the B theory fails its gate, the world closes immediately as a B gate failure.

There is no API path for submitting another theory after either failure.

This prevents the deterministic visible evaluator from becoming a free rejection-sampling oracle.

### Visible-fit thresholds

The single committed A theory must achieve >= **0.90 exact accuracy** on the 60 visible A observations.

The single committed B program must achieve >= **0.90 exact accuracy** on the 28 visible B-calibration observations.

These are construct-validity gates, not the primary endpoint.

---

## Condition-blind abstention

After exactly 60 A interventions and **before attempting the A theory gate**, the operating system may irreversibly return `no_concept`.

The option is available identically in causal and Null worlds. It does not consume the four A-gate units; all unused resources are forfeited when the run closes.

Once the A theory gate has been attempted, `no_concept` is no longer available.

For the Null-world false-positive calculation, a positive concept declaration is an **A theory accepted by the one-shot Broker gate**. Rejected theories and `no_concept` are not positives.

The eventual Conjecturer prompt may not mention Null worlds or suggest that a hidden concept exists.

---

## Frozen representation rule

The accepted A theory freezes all of the following:

- latent variable name/identity;
- domain kind;
- geometry;
- inferred cardinality;
- all entity assignments;
- A program.

The B theory must contain byte/structure-equivalent frozen latent metadata and assignments (apart from the Broker-controlled `frozen=true` flag) and an unchanged A program.

The representation therefore cannot be categorical in A and silently become ordered/numeric in B; its finite geometry is fixed before B data is exposed.

---

## Sealed D4 transfer

After the single B gate succeeds, the Broker issues 32 held-out Paradigm-B challenges: four interventions for each of the eight transfer entities.

All 32 predictions are generated deterministically from the committed Theory AST and frozen latent representation **before** any transfer outcome is requested from the Hidden World.

The operating agent never sees transfer outcomes before run closure.

Individual-world D4 qualification requires:

1. accepted one-shot A theory;
2. frozen latent representation with zero post-A edits;
3. accepted one-shot B theory;
4. disjoint nontrivial A/B operator signatures;
5. Z3 structural-isomorphism result `UNSAT`;
6. >= 0.90 exact accuracy on the 32 sealed B-transfer observations.

The per-world 0.90 threshold is not the primary comparative claim.

---

## Binding kill criteria

1. **Hallucination Kill:** high-confidence concept false-positive rate on Null Worlds >= 0.05.
2. **Critic Kill:** during later critic qualification, failure to find a falsifying intervention for deliberately injected structurally flawed theories in three consecutive eligible cycles.
3. **Baseline Kill:** across the preregistered 100-world comparison sample, if Flat LLM + symbolic/program synthesis achieves >= 0.90 sealed-B-transfer accuracy at a rate equal to or greater than Archimedes-Full, the V0 epistemic scaffold is deemed non-beneficial overhead.

The exact inferential statistical test for any publication-grade superiority claim must still be frozen before the first comparative model experiment.

---

## Prompt and causal isolation requirements

No Conjecturer or Critic interface may be implemented while referee status remains HOLD.

When/if authorized:

- Conjecturer and Critic must be separate stateless inference calls.
- No shared model session or hidden context may connect them.
- Only schema-valid AST artifacts and deterministic ledger results may cross component boundaries.
- The Conjecturer prompt must describe permitted inputs/actions and required outputs only.
- It may not contain the words or instructions that presuppose the solution, including directives to find a `hidden`, `latent`, `state`, `property`, `invariant`, or `concept`.
- The operating prompt must not disclose that Null Worlds exist.
- The model receives no generator source, hidden specs, seeds, validation reports, condition labels, ground-truth cardinality, or sealed outcomes.

Prompt text itself must be separately preregistered before the first model experiment.

---

## Pre-agent blinding requirements retained from V0.1.1

Agent-visible metadata must not reveal condition or generator seed:

- public `world_kind` is always `experimental`;
- benchmark world IDs are opaque and unrelated to condition/seed;
- filenames may not contain `null`, `causal`, or raw seed values;
- true condition, seed, hidden cardinality, q, programs, and validation reports remain trusted-side only.

---

## Current authorization boundary

**Referee decision entering V0.1.3: HOLD.**

V0.1.3 implements the requested safeguards only. It does **not** authorize or contain the Conjecturer/Critic prompts.

The next allowed action is referee evaluation of this frozen protocol and implementation. Only an explicit `AUTHORIZE NEXT IMPLEMENTATION STAGE` ruling permits agent-interface work.
