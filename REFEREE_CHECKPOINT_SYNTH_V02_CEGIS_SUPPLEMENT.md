# Archimedes V0.2 — Supplemental Synthesizer Algorithm Checkpoint

**Requested ruling:** AUTHORIZE CEGIS SUPPLEMENT / HOLD — REVISE / TERMINATE TOOL-ASSISTED V0  
**Current authorization:** V0.2 implementation and exactly one frozen qualification execution authorized.  
**Qualification status:** **NOT RUN.** `V02_QUALIFICATION_TRIGGER.txt` does not exist.  
**Archimedes benchmark status:** **NOT EXPOSED.** No causal or Null benchmark world has been shown to any language model.

## Why this checkpoint exists

The approved V0.2 design was implemented as a complete fixed-depth syntax skeleton in Z3 with the frozen grammar, fixed latent assignments, successive SAT checks, and the preregistered deterministic `rlimit=50,000,000`.

Before touching the frozen 1,000-AST qualification corpus, we exercised the implementation only on independent hand-written synthetic fixtures, as authorized.

A deliberately nontrivial depth-4 fixture

```text
permute(xor(rotl(q,1), a), [3,1,7,0,5,2,6,4])
```

was not solved within the frozen 50M Z3 `rlimit`. The solver returned `unknown` / `canceled` before producing a candidate. The same failure persisted under three logically equivalent fixed-skeleton encodings:

1. 3-bit BitVec semantics with full semantic commutativity ordering;
2. 3-bit BitVec semantics with a cheaper sound structural commutativity breaker;
3. finite-domain Int semantics with extensional 8-value / 8×8 operator tables.

Simple depth-2 two-variable laws do solve. The failure is therefore not a grammar-correctness issue; it is a search/constraint-propagation bottleneck caused by asking Z3 to solve the complete 31-slot depth-5 grammar against all observations simultaneously.

**No qualification-corpus expression or failed qualification item has been inspected.** These implementation failures occurred entirely on independent synthetic fixtures written before qualification.

Because proceeding with the current encoding would knowingly send a mechanically inadequate tool into the one-shot qualification, we are returning to the referee before making a material search-policy change.

---

# Proposed supplement: Counterexample-Guided Inductive Synthesis (CEGIS)

We propose retaining the approved bounded syntax-guided SMT formulation but changing **how observational constraints are introduced**.

The grammar, AST depth, operator vocabulary, solver, solver version, latent-partition firewall, objective order, qualification corpus, recovery threshold, and 50M cumulative `rlimit` remain unchanged.

Instead of asserting all observations into the SMT formula on the first check, V0.2 would use a deterministic CEGIS loop.

## 1. Fixed syntax search space

The candidate program remains a complete bounded Theory-AST skeleton:

- same public grammar;
- maximum depth 5 for qualification and 6 in V0;
- same operator semantics;
- no operator weights or frequencies;
- no generator priors;
- entity→latent assignments supplied as immutable constants;
- no partition variables.

CEGIS changes only the constraint-delivery strategy, not the hypothesis class.

## 2. Deterministic working set

Let the visible observations, in canonical order, be

`O = (o_0, ..., o_{n-1})`.

Initialize:

`W = {o_0}`.

No random seed, heuristic observation selection, information-gain score, or corpus-derived ordering is used.

Every time a candidate violates the current full-data requirement, append the **lexicographically first violating observation not already in W**.

Therefore `W` grows monotonically and can contain at most `n` observations.

## 3. Trusted external verifier

A SAT model is decoded into a legal Theory AST and executed by the existing deterministic trusted evaluator on **all** observations `O`.

The verifier reports internally only:

- full Hamming error;
- active AST node count;
- AST depth;
- canonical AST serialization;
- first unmet observation under canonical order.

These values are part of the normal synthesis invocation. They are not qualification-level feedback and are not emitted with corpus-item identities.

## 4. Exact CEGIS feasibility oracle for a Hamming bound

For a proposed Hamming bound `b`, the SMT problem asserts only

`sum_{o in W} [P(o) != y_o] <= b`

plus the frozen syntax/semantic constraints.

Then:

1. If SMT returns **UNSAT** on W, the full problem at bound b is also UNSAT because W is a subset of O. Thus b is infeasible.
2. If SMT returns **SAT**, decode P and evaluate it on all O.
3. If `Error_O(P) <= b`, b is feasible.
4. If `Error_O(P) > b`, then at least one mismatching observation lies outside W. Add the canonical first such observation to W and repeat the same bound.
5. If Z3 reaches the remaining cumulative `rlimit`, terminate and return the best full-data-valid incumbent found so far, or fail gracefully if none exists.

This oracle is sound and complete absent resource exhaustion. It cannot declare a bound feasible without full deterministic verification, and UNSAT on a subset is a valid proof of full infeasibility.

## 5. Hamming minimization

Use the same approved successive-SAT objective, implemented through the CEGIS feasibility oracle:

- binary search integer `b` over `[0,n]`;
- each feasibility query uses the current monotonically growing W;
- retain the best fully verified incumbent.

For the qualification corpus, a grammar-generated exact program exists, so `b=0` is theoretically feasible. This fact follows from corpus construction and was frozen before either V0.1 or V0.2 implementation; it is not derived from inspecting qualification outcomes.

## 6. Secondary objectives

After the minimum Hamming error `b*` is established, apply the same CEGIS oracle while adding candidate-independent structural bounds:

1. minimize active AST nodes;
2. minimize effective depth;
3. minimize canonical AST encoding field-by-field in the already frozen preorder selector/mapping traversal.

For a structural bound, a SAT candidate is accepted as feasible only if the trusted evaluator confirms full-data error `<= b*`. If not, add the first outside-W mismatch and repeat.

UNSAT on W under a structural bound proves that the stricter full problem is also UNSAT.

Thus the originally approved lexicographic objective remains:

`Hamming error -> active nodes -> depth -> canonical encoding`.

## 7. Resource accounting

The solver context remains exactly the frozen manifest:

- Python 3.12.14;
- `z3-solver==5.1.0.0`;
- `z3.Solver`;
- `auto_config=true`;
- `random_seed=0`;
- `timeout=0`;
- cumulative `rlimit=50,000,000` per synthesis invocation.

Every CEGIS SAT check consumes from the same single cumulative 50M allowance using Z3's deterministic `rlimit count` statistic. Rebuilding a solver does not reset the scientific budget.

The external deterministic evaluator is not an alternative search engine: it only executes a concrete returned AST on visible observations and supplies counterexamples.

Full and Flat receive the identical implementation and identical 50M solver budget.

## 8. No new tunable hyperparameters

The proposed loop introduces **no tunable batch size, restart count, heuristic score, operator weighting, or corpus-dependent threshold**.

Frozen choices are:

- initial W: first canonical observation;
- counterexample addition: exactly one, canonical first outside-W violation;
- Hamming bound search: deterministic integer binary search;
- objective order: already frozen;
- resource ceiling: already frozen;
- solver configuration: already frozen.

## 9. Qualification firewall remains unchanged

If this supplement is authorized:

1. implement it;
2. test only on independent synthetic fixtures and exhaustive small-depth grammar checks;
3. freeze the final implementation source hash;
4. create the qualification trigger **once**;
5. execute the same frozen 1,000-AST corpus once;
6. read only aggregate qualification output.

If recovery is `<0.95`, Tool-Assisted V0 is permanently abandoned. No failed corpus item may be inspected and there will be no V0.3 synthesizer.

---

# Requested ruling

## AUTHORIZE CEGIS SUPPLEMENT

The deterministic CEGIS working-set method is accepted as an implementation-level realization of the already authorized bounded syntax-guided SMT redesign. We may implement it and, after independent fixture validation, use it for the single frozen V0.2 qualification execution.

## HOLD — REVISE

The CEGIS method materially changes the preregistered V0.2 algorithm or creates a new researcher degree of freedom. Specify the required correction.

## TERMINATE TOOL-ASSISTED V0

The fixed-skeleton implementation failure on independent fixtures is sufficient reason to end the authorized redesign without consuming the qualification attempt.

**Benchmark execution remains prohibited under every ruling.**
