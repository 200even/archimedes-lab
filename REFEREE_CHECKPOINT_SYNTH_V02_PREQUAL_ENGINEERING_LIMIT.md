# Archimedes V0.2 — Prequalification Engineering Limit Checkpoint

**Status:** HOLD FOR REFEREE RULING — qualification has not been triggered.

**Requested ruling:** AUTHORIZE ONE FINAL SEMANTICS-PRESERVING ENGINEERING CORRECTION / PROCEED TO ONE-SHOT / TERMINATE TOOL-ASSISTED V0.

## 1. Binding context

The referee authorized the CEGIS supplement as the final architecture for `EnumerativeSynthesizer V0.2`, with:

- canonical `W = {o_0}` initialization;
- exactly the first canonical violating observation appended per CEGIS iteration;
- trusted full-`O` verification of every returned AST;
- one cumulative deterministic Z3 `rlimit = 50,000,000` per synthesis invocation;
- frozen `z3-solver==5.1.0.0` and solver parameters;
- independent synthetic-fixture testing before code freeze;
- exactly one subsequent execution on the frozen 1,000-AST qualification corpus;
- terminal abandonment of Tool-Assisted V0 if qualification recovery is `< 0.95`.

No causal or Null Archimedes benchmark world has been exposed. `V02_QUALIFICATION_TRIGGER.txt` has not been created, so the one-shot qualification has not been consumed.

## 2. Synthetic fixture that remains unsolved

The independent hard fixture is:

```text
permute(xor(rotl(q, 1), a), [3,1,7,0,5,2,6,4])
```

It is a depth-4 legal Theory-AST expression and is tested both in a depth-4 search skeleton and inside the qualification depth-5 skeleton. It was defined before any qualification exposure and does not originate from the frozen qualification corpus.

The required endpoint for this engineering fixture is a full-valid candidate within the frozen 50M cumulative Z3 resource envelope.

## 3. Engineering defects corrected before this checkpoint

All corrections below were derived solely from independent synthetic-fixture behavior. None used qualification-corpus items, hidden-world priors, benchmark outcomes, or LLM outputs.

### A. Cumulative `rlimit` accounting

Z3 5.1.0.0's reported `rlimit count` contains a pre-check baseline. Charging the raw statistic falsely exhausted the external cumulative ledger. The implementation now charges the measured `after - before` delta while still setting each fresh solver's native `rlimit` to the remaining invocation budget.

### B. Invocation-local solver context

Repeated identical simple synthesis calls previously recovered the same AST/truth table but took different numbers of SAT checks. Each synthesis invocation now receives a fresh Z3 `Context`, while preserving the frozen solver version, parameters, random seed, and cumulative budget.

This removed the replay nondeterminism on the independent XOR fixture.

### C. Semantically dead mapping constraints

Mapping entries on nodes whose selector is not `PERMUTE` are executable-semantic dead variables. Identity equalities on those dead variables were removed. This changes no Theory-AST behavior.

### D. Exact lexicographic score encoding

For a skeleton with at most `N` active nodes, the scalar

```text
score = Hamming_error * (N + 1) + active_nodes
```

is exactly order-isomorphic to the already-frozen first two objectives `(Hamming error, active-node count)`, since valid ASTs have `1 <= active_nodes <= N`.

The search can therefore constrain this scalar without changing the objective or hypothesis class. Depth and canonical encoding remain later tie-breakers.

### E. Exact partial-bijection projection on CEGIS `W`

For a `PERMUTE` node, a partial mapping on child values realized by `W` extends to a full 8-element permutation iff it is injective on those realized child values. The reduced-W solver therefore enforces injectivity only over values actually realized by W; the trusted decoder constructs the lexicographically smallest full bijection for unseen inputs.

This is an exact projection of the legal permutation hypothesis class onto W, not a relaxation of executable AST validity. Every decoded candidate remains a complete legal `PermutationExpr` before full-O evaluation.

## 4. Current synthetic result

After the corrections above, the general test suite reaches **41 passed / 2 failed**.

The only remaining failures are the same nested-permutation fixture:

- depth-4 search: 10 SAT checks, then `unknown / canceled` at the cumulative 50M rlimit, no full-valid candidate returned;
- depth-5 search: 10 SAT checks, then `unknown / canceled` at the cumulative 50M rlimit, no full-valid candidate returned.

The simple exhaustive depth-1 grammar, simple two-variable laws, partition immutability, and deterministic replay tests pass.

Relevant CI runs:

- Run #81, context-isolated hardened CEGIS: `33540468515` — 41 passed / 2 failed.
- Run #83, exact lexicographic score encoding: `33540790709` — 41 passed / 2 failed.
- Run #86, partial-bijection decoder corrected: `33541253164` — 41 passed / 2 failed.

The repeated 50M exhaustion after semantics-preserving reductions indicates a real remaining bounded-synthesis resource limit rather than the earlier bookkeeping/replay defects.

## 5. Why implementation is halted here

We are deliberately not continuing to invent search heuristics against this fixture. Repeated algorithmic changes, even against a benchmark-independent synthetic fixture, can eventually become an engineering analogue of overfitting and would violate the spirit of the one-redesign rule.

The frozen qualification corpus remains completely untouched by V0.2.

## 6. Proposed narrow correction if authorized

If the referee permits one final implementation correction before code freeze, we propose a **feasible-incumbent-first optimization schedule** while preserving all existing CEGIS and objective semantics.

Current search behavior can spend the entire 50M budget proving aggressive lower objective bounds before it has ever retained a full-O-valid incumbent. This is poorly aligned with the referee's explicit resource rule:

> if the rlimit is reached before optimization completes, return the best valid candidate found so far, or fail gracefully if no bounded candidate was discovered.

The proposed correction would:

1. first search deterministically for a full-O-valid legal AST under the broadest frozen objective bound;
2. retain that AST as the incumbent;
3. spend the remaining single 50M cumulative budget monotonically tightening the exact preregistered objective `(Hamming error, nodes, depth, canonical encoding)`;
4. if the rlimit expires, return the best full-O-valid incumbent found so far, exactly as previously authorized;
5. keep `W={o_0}`, first-canonical-counterexample selection, grammar, corpus, solver package/parameters, 50M cumulative rlimit, latent-partition firewall, and full-O trusted verification unchanged.

No target-specific operator ordering, structural template, grammar weighting, qualification statistic, or hidden-world prior would be introduced.

We will preregister the exact feasible-first schedule before implementing it if this option is selected.

## 7. Requested ruling

Please return one:

### A. AUTHORIZE ONE FINAL SEMANTICS-PRESERVING ENGINEERING CORRECTION

Authorize the feasible-incumbent-first schedule described above, after an exact schedule is documented before code modification. Synthetic fixtures may be rerun; qualification remains prohibited until all synthetic gates pass and the code hash is frozen.

### B. PROCEED TO ONE-SHOT QUALIFICATION AS-IS

Rule that the hard nested-permutation fixture is not a required prequalification gate. Freeze the current deterministic implementation and execute the frozen 1,000-AST corpus exactly once. The 95% terminal clause remains binding.

### C. TERMINATE TOOL-ASSISTED V0

Rule that failure to solve this independent legal depth-4 fixture within the frozen 50M budget demonstrates that V0.2 cannot be accepted as a sufficiently competent law-fitting tool. Tool-Assisted V0 is abandoned without consuming the qualification corpus.

## 8. Explicit non-actions

Pending this ruling we will not:

- create `V02_QUALIFICATION_TRIGGER.txt`;
- inspect or run V0.2 against any item in the frozen qualification corpus;
- increase the 50M rlimit;
- change the public Theory-AST grammar;
- lower the 95% qualification threshold;
- alter the corpus or its digest;
- expose any causal or Null Archimedes benchmark world;
- introduce target-specific heuristics based on the nested-permutation fixture.
