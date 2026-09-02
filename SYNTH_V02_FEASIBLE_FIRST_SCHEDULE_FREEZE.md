# EnumerativeSynthesizer V0.2 — Feasible-First Schedule Freeze

**Status:** AMENDED AND FROZEN BEFORE EXACT-FIRST IMPLEMENTATION

This document preregisters the exact deterministic search sequence authorized for the final prequalification engineering correction to `EnumerativeSynthesizer V0.2`.

The original feasible-first schedule was frozen before implementation. After independent synthetic validation showed that midpoint Hamming bounds could consume the resource budget while a trivial fallback incumbent existed, the referee authorized one and only one schedule clarification: query the mathematical Hamming lower bound `E <= 0` immediately after the fallback incumbent, before any intermediate Hamming bound.

Nothing in this amendment changes the Theory AST grammar, latent-partition firewall, candidate semantics, objective hierarchy, qualification corpus, qualification threshold, Z3 package/version, CEGIS counterexample policy, or cumulative solver resource limit. It changes only the deterministic order in which already-authorized feasibility and optimization constraints are presented to Z3.

## Frozen resources and ordering

- Z3 package: `z3-solver==5.1.0.0`
- Solver: `z3.Solver`
- `auto_config=true`
- `random_seed=0`
- no wall-clock timeout
- one cumulative deterministic `rlimit=50,000,000` per `search()` invocation, shared across every SAT/UNSAT check in every phase
- CEGIS working set starts with exactly the first canonically ordered observation: `W={o_0}`
- whenever a SAT model violates the full observation set `O` under the currently tested bound, append exactly the first canonical violating observation not already in `W`
- all returned models are decoded and checked by the trusted Python evaluator against full `O`
- no stochastic restart, alternate solver, target-specific rule, operator preference, structural template, grammar weighting, or qualification-derived heuristic is permitted
- if any required Z3 check returns `unknown` or exhausts the cumulative resource ledger, optimization terminates immediately and the best full-`O`-verified legal incumbent found so far is returned; if no such incumbent exists, the search fails gracefully

For any verified candidate `c`, define the trusted score tuple

`S(c) = (E(c), N(c), D(c), C(c))`

where:

- `E(c)` is full-`O` Hamming error,
- `N(c)` is active AST node count,
- `D(c)` is AST depth,
- `C(c)` is the existing frozen canonical AST serialization order.

The anytime incumbent is always the lexicographically smallest `S(c)` among all full-`O`-verified candidates encountered so far.

## Frozen sequence

The sequence is exactly:

**Fallback -> `E <= 0` -> binary tightening of any remaining Hamming interval -> node tightening -> depth tightening -> canonical tie-break.**

No phase may be reordered or skipped except where a preceding result mathematically fixes the optimum, as specified below.

## Phase 0 — Establish a fallback incumbent

Before attempting any optimized bound, perform one CEGIS feasibility search with the maximally permissive bounds allowed by the frozen hypothesis class:

- Hamming bound: `E <= |O|`
- no effective node-count minimization; membership in the frozen maximum AST skeleton only
- no effective depth minimization; membership in the frozen maximum AST skeleton only
- no canonical-prefix restriction

Every SAT model is decoded and verified against full `O`. The first full-`O`-verified legal candidate becomes the initial anytime incumbent.

If this phase returns `unknown` or exhausts the cumulative rlimit before producing an incumbent, the invocation fails gracefully. No later phase is entered.

## Phase 1A — Exact-first Hamming query

Immediately after Phase 0, issue exactly one CEGIS feasibility query at the mathematical lower bound:

- `E <= 0`
- `node_bound = None`
- `depth_bound = None`
- no canonical-prefix restriction

The only structural restrictions are those intrinsic to the already-frozen maximum syntax skeleton and legal Theory AST grammar. In particular, **no node-count or depth minimization constraint is permitted on this query**.

Outcomes:

1. **Feasible:** verify the candidate against full `O`, update the incumbent, set `E* = 0`, and skip Phase 1B because zero is the mathematical minimum Hamming error.
2. **Proven infeasible:** proceed to Phase 1B over the remaining interval `[1, e_inc]`, where `e_inc` is the current incumbent's verified Hamming error.
3. **Unknown / cumulative rlimit exhausted:** terminate optimization immediately and return the current fallback incumbent.

No alternative exact-fit query, restart, or different constraint encoding is allowed.

## Phase 1B — Binary tightening of the remaining Hamming interval

This phase is entered **only** if `E <= 0` was proven infeasible.

Let the current incumbent's verified Hamming error be `e_inc`. Initialize:

- `lo = 1`
- `hi = e_inc`

While `lo < hi`:

1. set `mid = floor((lo + hi) / 2)`;
2. run deterministic CEGIS under `E <= mid` with `node_bound = None`, `depth_bound = None`, and no canonical-prefix restriction;
3. if full-`O` feasibility is established, update the incumbent if the verified candidate improves `S(c)` and set `hi = min(mid, E(candidate))`;
4. if the working-set constraints are proven UNSAT, set `lo = mid + 1`;
5. if the solver returns `unknown` or the cumulative rlimit is exhausted, terminate and return the current incumbent.

When `lo == hi`, set `E* = lo`, provided the phase completed without `unknown`. If the incumbent does not yet realize `E*`, issue exactly one witness query at `E <= E*`, still with `node_bound = None` and `depth_bound = None`. If that witness query cannot complete, return the current incumbent.

No node-count, depth, operator, or canonical preference is used during Hamming minimization.

## Phase 2 — Minimize active node count

Only after `E*` has been established, minimize node count while preserving `E <= E*`.

1. initialize `lo = 1`, `hi = N(incumbent)`;
2. while `lo < hi`:
   - set `mid = floor((lo + hi) / 2)`;
   - run deterministic CEGIS with `E <= E*`, `N <= mid`, and no tighter depth constraint than the frozen maximum skeleton;
   - on feasible, update the incumbent if `S(c)` improves and set `hi = min(mid, N(candidate))`;
   - on UNSAT, set `lo = mid + 1`;
   - on `unknown` or cumulative rlimit exhaustion, terminate and return the current incumbent.
3. the completed optimum is `N* = lo`.

If the incumbent does not realize `N*`, issue exactly one witness query at `E <= E*`, `N <= N*`, with no tighter depth constraint. If that query cannot complete, return the current incumbent.

## Phase 3 — Minimize depth

Only after `E*` and `N*` are established, minimize depth.

1. initialize `lo = 1`, `hi = D(incumbent)`;
2. while `lo < hi`:
   - set `mid = floor((lo + hi) / 2)`;
   - run deterministic CEGIS with `E <= E*`, `N <= N*`, `D <= mid`;
   - on feasible, update the incumbent if `S(c)` improves and set `hi = min(mid, D(candidate))`;
   - on UNSAT, set `lo = mid + 1`;
   - on `unknown` or cumulative rlimit exhaustion, terminate and return the current incumbent.
3. the completed optimum is `D* = lo`.

If the incumbent does not realize `D*`, issue exactly one witness query at the fixed `E*`, `N*`, and `D*` bounds. If that query cannot complete, return the current incumbent.

## Phase 4 — Canonical AST tie-break

Only after `E*`, `N*`, and `D*` are established, apply the already-frozen canonical preorder tie-break under those fixed bounds.

Canonicalization proceeds in the existing frozen order:

1. preorder AST node traversal;
2. minimize selector value at each active node using deterministic integer feasibility checks;
3. for `permute`, minimize mapping entries in source order `0..7` using deterministic feasibility checks;
4. recurse into active children left-to-right.

Every feasibility result is checked against full `O`. On `unknown` or cumulative rlimit exhaustion, return the current best verified incumbent without restarting or changing the search order.

## Multiple-candidate requests

For `limit > 1`, after a candidate is returned, block exactly that encoded AST using the existing deterministic AST block and repeat Phases 0–4 under the same single search invocation resource policy already defined by the implementation. No semantic or operator-specific neighborhood search is introduced.

The qualification run uses `limit=1` as already frozen.

## Qualification and terminal rule

After implementation of this exact schedule:

1. run only independent synthetic fixtures and exhaustive small-depth grammar tests;
2. require the synthetic test suite to pass;
3. freeze the implementation commit/hash and solver manifest;
4. create `V02_QUALIFICATION_TRIGGER.txt` exactly once;
5. execute the frozen 1,000-AST qualification corpus exactly once;
6. recovery `>= 0.95` qualifies Tool-Assisted V0;
7. recovery `< 0.95` permanently abandons Tool-Assisted V0; there is no V0.3.

No causal or Null Archimedes benchmark world may be exposed during any of these steps.