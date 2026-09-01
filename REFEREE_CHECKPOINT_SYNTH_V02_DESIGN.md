# Archimedes V0 — EnumerativeSynthesizer V0.2 Algorithmic Preregistration

**Requested ruling:** AUTHORIZE V0.2 IMPLEMENTATION / HOLD — REVISE / REJECT TOOL-ASSISTED V0  
**Current authorization:** Exactly one benchmark-independent synthesizer redesign is permitted.  
**Implementation status:** **No V0.2 synthesizer code has been written.**  
**Benchmark status:** No causal or Null Archimedes benchmark world has been exposed to any language model.

## Purpose

`EnumerativeSynthesizer V0.1` failed the frozen engineering qualification: its best preregistered ceiling recovered 82.6% of the fixed 1,000-expression corpus, below the frozen 95% threshold.

We have not inspected individual qualification failures or changed the corpus, grammar, threshold, or Archimedes benchmark. The redesign below is based on a general limitation visible directly in the V0.1 algorithm: V0.1 performs heuristic beam search over intermediate expressions ranked by current visible fit. Consequently, a subtree that is necessary for a correct deeper program can be permanently discarded merely because that subtree is not itself predictive of the final output.

V0.2 therefore removes heuristic beam selection entirely. The proposed change is from **heuristic enumerative search** to **complete bounded syntax-guided constraint synthesis** over the already-frozen Theory AST grammar.

The repository name `EnumerativeSynthesizer V0.2` is retained for continuity, but its search engine will be a bounded SMT/SAT-style synthesizer.

---

## 1. Core algorithm

For each LLM-proposed latent representation, compile the permitted program search into a finite constraint problem.

### 1.1 Fixed expression skeleton

For maximum permitted expression depth `D`, construct a complete binary-tree skeleton with:

`2^D - 1`

node positions.

Each node has an `active` bit and a symbolic operator selector. The frozen grammar determines the only legal node kinds:

**Leaves**

- latent variable `q`;
- intervention variable (`x` in A, `u` in B);
- constants `0..7`.

**Unary operators**

- `rotl` with shift in `{1,2}`;
- `permute` with a bijection over `{0,...,7}`.

**Binary operators**

- `add_mod`;
- `mul_mod`;
- `xor`;
- `bit_and`;
- `bit_or`;
- `min_u3`;
- `max_u3`;
- `abs_diff`;
- `eq_mask`.

Operator arity controls which descendants are active:

- leaf: no active children;
- unary: one active child;
- binary: two active children.

Inactive descendants are forced to one canonical dummy encoding so that syntactically irrelevant values cannot create duplicate models.

This skeleton is purely a representation of the existing bounded grammar. It adds no operator, template, or Hidden World prior.

### 1.2 Exact finite semantics

For every supplied observation `(q, action, y)` and every active skeleton node, introduce a 3-bit value constrained by the exact deterministic semantics already used by `theory_eval.py`.

Examples:

- `add_mod(a,b) = (a+b) mod 8`;
- `xor(a,b) = a XOR b`;
- `rotl(a,r)` is the frozen 3-bit rotation;
- `eq_mask(a,b) = 7` if equal, otherwise `0`.

A `permute` node receives eight symbolic output values constrained to be a permutation of `0..7`; its output is the indexed image of its child value.

No learned surrogate, approximate evaluator, stochastic search, or operator weighting is introduced.

### 1.3 Soundness and completeness invariant

The implementation must satisfy two deterministic test obligations before qualification execution:

1. **Soundness:** every satisfying model decodes to a Theory AST accepted by the frozen schema and its decoded AST has exactly the same truth-table semantics as the solver model.
2. **Bounded completeness:** every valid Theory AST of depth at most `D` has at least one satisfying encoding in the skeleton.

These properties will be tested on exhaustive small-depth grammars and hand-constructed expressions without using the frozen 1,000-expression qualification corpus.

---

## 2. Why this addresses the V0.1 plateau

V0.1 must choose a small set of intermediate expressions before constructing deeper expressions. It ranks these intermediates by their immediate agreement with the observations. This is an incomplete search rule: useful latent algebraic subexpressions can have poor marginal predictive accuracy before being combined with another subtree.

V0.2 never discards a legal subtree because of its intermediate predictive score. The solver reasons over the complete bounded expression simultaneously.

Syntactic variants such as:

`x XOR q`

and

`q XOR x`

remain logically equivalent alternatives inside the constraint system rather than consuming separate positions in an external beam. The solver is free to prune them internally through constraint propagation.

We additionally propose only the following **semantics-preserving, grammar-general symmetry breakers**:

- for operators that are mathematically commutative on the frozen domain, impose a canonical ordering on child encodings;
- canonicalize inactive descendants;
- canonicalize unused operator parameters;
- constrain permutation parameters to one explicit bijection representation.

No associativity, distributivity, De Morgan, operator-frequency, generator-template, or qualification-failure-specific rewrite rules will be added.

---

## 3. Deterministic objective for noisy visible data

The qualification corpus evaluates exact full-domain semantic recovery, but real V0 observations contain the already-frozen measurement noise. The synthesizer therefore requires a deterministic ranking rule.

For a fixed LLM-proposed latent partition, candidate programs are ordered lexicographically by:

1. **minimum visible Hamming error**;
2. **minimum number of active AST nodes**;
3. **minimum effective AST depth**;
4. **lexicographically smallest canonical AST encoding**.

We propose implementing this without Z3 `Optimize` so the objective is explicit and auditable.

The solver will use successive ordinary satisfiability checks:

1. find the minimum achievable Hamming-error bound;
2. under that bound, find the minimum active-node count;
3. under those bounds, find the minimum effective depth;
4. fix remaining selector/parameter variables in a preregistered lexicographic order by repeatedly choosing the smallest satisfiable value.

The resulting first program is therefore deterministic for a fixed input and frozen solver build.

To return additional candidates, block the **complete finite truth-table semantics** of the accepted program and repeat the same optimization procedure until either 32 semantically distinct programs have been returned or no additional satisfying program exists.

Thus syntactically different programs with exactly the same finite behavior do not occupy multiple candidate slots.

---

## 4. Qualification mode

The frozen qualification corpus consists of 1,000 ASTs sampled independently from the frozen qualification grammar and evaluated on the complete 8x8 input grid.

V0.2 qualification will not introduce a new tuning ladder.

For each qualification item:

1. supply its complete 8x8 truth table to the same V0.2 program-search engine;
2. use the frozen qualification maximum target depth (`<=5`);
3. ask for the deterministic best program;
4. count recovery iff the returned program's complete 8x8 truth table is exactly equal to the target truth table.

The aggregate pass criterion remains exactly:

`recovery_rate >= 0.95` over the same 1,000 items.

The corpus digest, seed, item order, grammar, and pass threshold remain unchanged.

There will be **one V0.2 qualification execution** after implementation and non-corpus unit verification. If it scores below 95%, Tool-Assisted V0 is abandoned as required by the referee.

### Solver exhaustion

A solver failure, unsupported result, or resource exhaustion counts as a qualification failure for that item. It may not be rerun with relaxed settings.

We propose freezing the exact Z3 package version and solver parameters before the qualification run. We do **not** propose selecting those parameters by trying alternatives on the frozen corpus.

---

## 5. Latent-partition firewall

V0.2 does not search over latent cardinality or entity assignments.

The LLM must first provide the candidate Theory AST containing:

- `k_hat`;
- one assignment for every entity;
- the frozen representation domain and geometry.

Only after that proposal exists may V0.2 fit the algebraic program conditional on those assignments.

For B, the Broker-frozen A representation is supplied unchanged. V0.2 may fit the B law but may not alter:

- `k_hat`;
- entity assignments;
- latent domain;
- latent geometry;
- frozen A program.

The phrase “blind to latent-partition assignments” is therefore interpreted operationally as **no partition search, alteration, merge, split, or scoring across alternative partitions by the synthesizer**. The synthesizer necessarily consumes the already-committed assignments in order to translate an entity observation into its proposed `q` value.

### Referee question 1

Is this interpretation of the latent-partition firewall correct?

---

## 6. No benchmark or qualification-specific priors

The V0.2 solver receives only:

- the public AST grammar;
- the LLM-proposed representation;
- the currently visible observations;
- fixed program-depth limits.

It does not receive:

- Hidden World source code;
- Hidden World generator distributions;
- generator templates;
- benchmark seeds;
- causal/Null condition labels;
- transfer observations;
- qualification-corpus identity;
- aggregate operator frequencies;
- individual V0.1 qualification failures;
- heuristics inferred from those failures.

Every operator is represented because it exists in the public grammar, not because of observed benchmark frequency.

---

## 7. Architectural parity

The identical V0.2 implementation, solver version, solver parameters, candidate limit, and program-depth limit will be used by Full and Flat.

The synthesizer remains a deterministic external compiler. It receives no conversation state and makes no language-model calls.

The number and placement of synthesis opportunities will remain identical across the two arms.

We will record per invocation:

- solver status;
- solver resource counters where available;
- number of SAT checks;
- returned candidate count;
- selected program objective tuple;
- synthesizer source SHA;
- solver package/version;
- solver-parameter manifest hash.

No difference in solver configuration may be selected conditionally on the experimental arm.

### Referee question 2

Is identical algorithm/configuration/access sufficient mechanical-compute parity, or must V0 additionally impose a deterministic solver-resource ceiling per invocation?

If a resource ceiling is mandatory, we request that the referee specify whether a fixed Z3 `rlimit`, rather than wall-clock time, is the preferred reproducible quantity. We will freeze it before implementation testing against the qualification corpus.

---

## 8. Permitted pre-qualification verification

Before the one allowed qualification execution, implementation testing will be restricted to synthetic fixtures created independently of the frozen 1,000-item corpus:

- each primitive operator;
- nested unary/binary expressions chosen manually;
- exhaustive grammar enumeration at very small depth where brute-force comparison is tractable;
- soundness checks against `theory_eval.py`;
- bounded-completeness checks at small depth;
- deterministic replay;
- semantic blocking of duplicate truth tables;
- partition-immutability tests.

These fixtures will not use the qualification seed, corpus items, generator priors, or Archimedes worlds.

No algorithmic parameter will be selected by measuring recovery on the frozen qualification corpus prior to the single final V0.2 qualification execution.

---

## 9. What is deliberately not changing

V0.2 does **not** change:

- the Theory AST grammar;
- operator vocabulary;
- distractors;
- domain size;
- maximum Archimedes expression depth;
- qualification corpus;
- qualification seed;
- qualification threshold;
- latent-cardinality rules;
- Broker budgets;
- A/B split;
- Z3 A/B non-isomorphism adjudication;
- model choice;
- prompts;
- Full/Flat inference budgets;
- causal or Null world generator.

No language model will see an Archimedes world during this redesign.

---

# Requested ruling

Please return one:

## AUTHORIZE V0.2 IMPLEMENTATION

The bounded syntax-guided constraint-synthesis design is a sufficiently general algorithmic improvement, preserves the concept/law-fitting firewall, and may be implemented. After independent unit verification, it may be run exactly once on the frozen 1,000-item qualification corpus.

This does **not** authorize Archimedes benchmark exposure.

## HOLD — REVISE

The theoretical design introduces an unacceptable completeness, determinism, compute-parity, or leakage issue. Specify the exact mandatory revision before code is written.

## REJECT TOOL-ASSISTED V0

Even under this design, deterministic synthesis cannot be isolated cleanly enough from the concept-discovery construct to justify the one-shot V0.2 attempt.

We specifically request rulings on:

1. whether consuming but never searching/modifying the LLM-proposed partition satisfies the latent-partition firewall;
2. whether identical deterministic solver configuration is sufficient mechanical-compute parity, or a fixed solver-resource ceiling must also be preregistered.
