# Archimedes V0.1.3 — Referee Checkpoint

**Requested ruling:** AUTHORIZE NEXT IMPLEMENTATION STAGE / HOLD  
**Current ruling entering this checkpoint:** HOLD  
**Agent status:** No Conjecturer or Critic prompt has been written or run.

## Response to mandatory revisions

We accept the referee's HOLD ruling and implemented only the requested pre-agent safeguards. V0.1.3 makes three binding changes: inferred latent cardinality under a hard anti-memorization cap, resource-priced one-shot visible-fit gates, and Z3 adjudication of A/B structural isomorphism.

The complete binding specification is in `PRE_REGISTRATION_FREEZE.md`.

---

## 1. Latent-cardinality safeguard

The referee authorized A2 and required either MDL or a hard cap satisfying:

`k_max <= floor(sqrt(|E|))`.

We chose the hard-cap option for V0 because it is deterministic and introduces fewer model-selection degrees of freedom than an MDL coding scheme.

With `|E| = 16`:

`2 <= k_hat <= 4`.

The Theory AST rejects any candidate outside this range. It also requires:

- every declared state `0..k_hat-1` to be used;
- at least two entities assigned to every state;
- exactly one assignment for all 16 entities;
- frozen domain kind `finite_discrete`;
- frozen geometry `unsigned_bitvector3`.

The hidden-world generator was correspondingly revised so causal benchmark worlds sample:

`k_true ∈ {2,3,4}`

without exposing `k_true` in public metadata. Hidden state populations are near-balanced and each state appears on both sides of the B calibration/transfer split.

Once an A theory is accepted, the Broker freezes **cardinality, domain, geometry, assignments, and A program**. Any attempted change in B fails irreversibly.

### Referee question 1

Does the hard-cap rule plus minimum two-entity reuse sufficiently implement the approved alternative to MDL for V0, or is an explicit description-length score still mandatory despite the referee's earlier allowance for a hard cap?

---

## 2. Rejection-sampling firewall

The prior `>= 0.90` visible-fit gate was vulnerable because a caller could submit an unlimited sequence of theories until one happened to pass.

V0.1.3 makes evaluation itself a scarce resource.

The same total **128-unit** budget is now partitioned as:

- 60 A-discovery interventions
- 4 units: single A-theory evaluation
- 28 B-calibration interventions
- 4 units: single B-theory evaluation
- 32 sealed B-transfer interventions

Thus:

`60 + 4 + 28 + 4 + 32 = 128`.

For each visible-fit gate:

1. The Broker permits exactly **one** attempt.
2. The four-unit charge occurs **before** schema parsing, structural validation, or fit scoring.
3. A malformed AST therefore costs the same as a well-formed AST.
4. A theory below 0.90 exact visible fit closes the world.
5. A structurally invalid theory closes the world.
6. There is no API transition back to discovery/calibration and no second submission path.

The `no_concept` abstention remains available after the 60 A observations only **before** the A gate is attempted. Attempting the gate irrevocably gives up the abstention option.

This means the visible evaluator provides at most one bit of actionable selection information per phase: survive or terminate. It cannot be used as an iterative hyperparameter oracle.

### Referee question 2

Is a four-unit one-shot charge per gate an adequate implementation of the requirement that visible evaluation consume experimental budget? In particular, does reducing discovery/calibration from 64/32 to 60/28 introduce a new comparability problem that should be handled differently?

---

## 3. SMT/Z3 non-isomorphism adjudication

Simple disjoint AST operator names do not prove that two explanations are mathematically distinct. V0.1.3 therefore adds a finite structural-isomorphism query implemented in Z3.

For the candidate theory, construct complete finite truth tables over its frozen inferred cardinality:

`T_A(q,a)` and `T_B(q,a)`

for:

- every `q ∈ {0,...,k_hat-1}`;
- every intervention symbol `a ∈ {0,...,7}`.

The solver searches for bijections:

- `phi_q` over latent labels;
- `phi_a` over intervention symbols;
- `phi_y` over output symbols;

such that:

`phi_y(T_A(q,a)) = T_B(phi_q(q), phi_a(a))`

for **every** latent/action pair.

All three mappings are constrained as finite permutations.

Interpretation:

- **SAT:** an opaque relabeling exists; the paradigms are structurally isomorphic and the D4 theory is rejected.
- **UNSAT:** no such relabeling exists; the theory may proceed if all other gates pass.

The trusted ledger records the Z3 status and SHA-256 digests of both finite truth tables.

The same SMT filter is applied to generated ground-truth worlds before admission, preventing the benchmark from demanding a non-isomorphism property that its own true explanation cannot satisfy.

The previous simpler requirement is also retained: nontrivial A and B operator signatures must be nonempty and disjoint.

### Referee question 3

Is this equivalence relation strong enough to close the algebraic-isomorphism loophole? We deliberately permit arbitrary relabeling of q, intervention, and output symbols because all are semantically opaque. Should the isomorphism group be broader or narrower?

---

## 4. B2 distractor operator vocabulary

The Theory AST now exposes same-domain distractors in addition to the true-generator-capable primitives.

Generator-capable primitives:

- `add_mod`
- `mul_mod`
- `xor`
- `rotl`
- `permute`

Distractors:

- `bit_and`
- `bit_or`
- `min_u3`
- `max_u3`
- `abs_diff`
- `eq_mask`

All operators map the same finite 3-bit domain to itself. No distractor is trivially disqualified by requiring floating point, strings, geometry, trigonometry, or another foreign type.

The hidden generator does not use the distractors.

### Referee question 4

Are these distractors sufficiently plausible for B2, or do any create a new shortcut or fail to provide meaningful structural competition?

---

## 5. Frozen representation geometry

The referee noted that freezing assignments alone was insufficient: the representation could otherwise be treated categorically in A and numerically in B.

V0.1.3 freezes:

- `domain_kind = finite_discrete`
- `geometry = unsigned_bitvector3`
- `cardinality = k_hat`
- every entity assignment

as part of the A-theory identity digest.

B submission must reproduce the same representation exactly apart from the Broker-controlled frozen flag.

### Referee question 5

Is `unsigned_bitvector3` an acceptable frozen geometry for V0, or does exposing that geometry leak too much about the hypothesis language? If too revealing, what bounded geometry would preserve deterministic execution without reintroducing the A/B semantic-switch loophole?

---

## 6. Prompt leakage remains outside authorization

No agent prompt has been implemented.

If V0.1.3 is authorized, prompt text will be a separate preregistration artifact before any model run. It will not mention Null worlds or instruct the model to find a hidden variable, state, property, invariant, or concept.

The operating instruction will be framed around predicting future intervention outcomes, with machine-readable interfaces supplied only as necessary for execution.

We are not requesting approval of any prompt in this checkpoint.

---

## 7. Verification status

The repository now contains tests for:

- cardinality cap and per-state reuse;
- hidden cardinality sampling and stratified B splitting;
- deterministic hidden-world replay;
- Z3 detection of isomorphism under opaque relabeling;
- Z3 proof of non-isomorphism for structurally different finite tables;
- one-shot A gate failure closing the world;
- frozen representation immutability across A→B;
- exact budget exhaustion on a valid D4 path;
- theory-derived sealed transfer predictions;
- condition-blind abstention;
- schema hash freezing.

GitHub CI passed the integrated V0.1.3 test suite before this checkpoint was submitted.

---

## Requested ruling

Please evaluate adversarially and return one of:

### AUTHORIZE NEXT IMPLEMENTATION STAGE

The three mandatory loopholes are sufficiently closed. We may implement, but not yet run, the isolated Conjecturer/Critic interfaces and separately preregister their prompts.

### HOLD — REVISE

One or more V0.1.3 safeguards remains insufficient. Specify the exact mandatory revision before any agent-interface work.

### REJECT V0

The bounded benchmark can no longer validly distinguish D4 explanatory transfer from sophisticated fitting even with these safeguards.

We specifically request that authorization not be granted merely because the implementation is rigorous. The question is whether a positive V0 result would survive the strongest plausible alternative explanation of memorization, rejection sampling, or algebraic disguise.
