# EnumerativeSynthesizer V0.2 — Feasible-First Schedule Freeze

**Status:** FROZEN BEFORE IMPLEMENTATION

This document preregisters the exact deterministic search sequence authorized as the final prequalification engineering correction for `EnumerativeSynthesizer V0.2`.

Nothing in this schedule changes the Theory AST grammar, latent-partition firewall, candidate semantics, objective hierarchy, qualification corpus, qualification threshold, Z3 package/version, or cumulative solver resource limit. It changes only the order in which already-authorized feasibility and optimization constraints are presented to Z3.

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
- no stochastic restart, alternate solver, target-specific rule, operator preference, structural template, or grammar weighting is permitted
- if any required Z3 check returns `unknown` or exhausts the cumulative resource ledger, optimization terminates immediately and the best full-`O`-verified legal incumbent found so far is returned; if no such incumbent exists, the search fails gracefully

For any verified candidate `c`, define the trusted score tuple

`S(c) = (E(c), N(c), D(c), C(c))`

where:

- `E(c)` is full-`O` Hamming error,
- `N(c)` is active AST node count,
- `D(c)` is AST depth,
- `C(c)` is the existing frozen canonical AST serialization order.

The anytime incumbent is always the lexicographically smallest `S(c)` among all full-`O`-verified candidates encountered so far.

## Phase 0 — Establish a feasible incumbent

Before attempting to prove any lower bound, perform one CEGIS feasibility search with the maximally permissive bounds allowed by the frozen hypothesis class:

- Hamming bound: `E <= |O|`
- active-node bound: `N <= N_max`, where `N_max = 2^max_depth - 1`
- depth bound: `D <= max_depth`
- no canonical-prefix restriction

Because these bounds impose no optimization preference beyond membership in the existing legal grammar, this phase asks only for any legal bounded AST. Every SAT model is decoded and verified against full `O`. The first full-`O`-verified legal candidate becomes the initial incumbent.

If this phase returns `unknown` or exhausts the cumulative rlimit before producing an incumbent, the invocation fails gracefully. No later optimization phase is entered.

## Phase 1 — Minimize full-observation Hamming error

Let the incumbent's verified error be `e_inc`.

Search for the minimum feasible Hamming bound by deterministic binary tightening over integer bounds:

1. initialize `lo = 0`, `hi = e_inc`;
2. while `lo < hi`:
   - set `mid = floor((lo + hi) / 2)`;
   - run the same deterministic CEGIS feasibility procedure under `E <= mid`, with `N <= N_max` and `D <= max_depth`;
   - if full-`O` feasibility is established, update the incumbent if the verified candidate improves `S(c)`, and set `hi = min(mid, E(candidate))`;
   - if the working-set constraints are proven UNSAT, set `lo = mid + 1`;
   - if the solver returns `unknown` or the cumulative rlimit is exhausted, terminate and return the current incumbent.
3. when `lo == hi`, the minimum Hamming bound is `E* = lo`, provided the phase completed without `unknown`.

No node-count or operator preference is used to select Hamming bounds.

## Phase 2 — Minimize active node count

Only after `E*` has been established, minimize node count while preserving `E <= E*`.

1. initialize `lo = 1`, `hi = N(incumbent)`;
2. while `lo < hi`:
   - set `mid = floor((lo + hi) / 2)`;
   - run deterministic CEGIS with `E <= E*`, `N <= mid`, and `D <= max_depth`;
   - on feasible, update the incumbent if `S(c)` improves and set `hi = min(mid, N(candidate))`;
   - on UNSAT, set `lo = mid + 1`;
   - on `unknown` or cumulative rlimit exhaustion, terminate and return the current incumbent.
3. the completed optimum is `N* = lo`.

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

After implementation:

1. run only independent synthetic fixtures and exhaustive small-depth grammar tests;
2. require the synthetic test suite to pass;
3. freeze the implementation commit/hash and solver manifest;
4. create `V02_QUALIFICATION_TRIGGER.txt` exactly once;
5. execute the frozen 1,000-AST qualification corpus exactly once;
6. recovery `>= 0.95` qualifies Tool-Assisted V0;
7. recovery `< 0.95` permanently abandons Tool-Assisted V0; there is no V0.3.

No causal or Null Archimedes benchmark world may be exposed during any of these steps.
