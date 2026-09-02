# Referee Checkpoint — V0.2 Feasible-First Synthetic Validation Failure

**Requested ruling:** CLARIFY FINAL SCHEDULE / TERMINATE TOOL-ASSISTED V0

## Exposure status

- The frozen 1,000-AST qualification corpus has **not** been executed.
- `V02_QUALIFICATION_TRIGGER.txt` does **not** exist.
- No causal or Null Archimedes benchmark world has been exposed to any language model.
- This failure was observed only on the already-existing independent synthetic fixtures in `tests/test_synthesis.py`.

## What was preregistered

Before code modification, the exact schedule was frozen in:

`SYNTH_V02_FEASIBLE_FIRST_SCHEDULE_FREEZE.md`

The frozen sequence was:

1. obtain any full-O-verified legal bounded AST under maximally permissive bounds `E <= |O|`, `N <= N_max`, `D <= max_depth`;
2. binary-tighten Hamming error from `[0, E(incumbent)]`;
3. binary-tighten node count;
4. binary-tighten depth;
5. apply the existing canonical AST tie-break;
6. on any `unknown`/rlimit exhaustion, return the best full-O-verified incumbent found so far.

The implementation follows that schedule literally.

## Synthetic result

CI run 91 on commit `f638f4c3c6b9345830ef089444794b4b32485bb6` failed 3 of 43 tests.

The important change is that the anytime policy now works mechanically: all three failing synthesis tests returned a legal full-O-verified incumbent rather than returning no candidate. However, the incumbent was poor and the first Hamming-tightening check consumed the remaining solver budget before a better full-O candidate was found.

Observed failures:

- simple `add_mod(q,a)` depth-2 fixture: returned accuracy `0.125` instead of `1.0` under the existing 5M synthetic fixture rlimit;
- nested-permutation depth-4 fixture: returned accuracy `0.125` instead of `1.0` under 50M;
- same nested-permutation fixture inside a depth-5 skeleton: returned accuracy `0.125` instead of `1.0` under 50M.

The remaining 40 tests passed.

## Diagnosis

The implementation exposed an ambiguity in the phrase "feasible incumbent first."

Our frozen Phase 0 interpreted "feasible" as *any legal AST verified against full O*, because `E <= |O|` is the maximally permissive Hamming constraint. That guarantees an anytime fallback, but it can establish a scientifically useless high-error incumbent. Binary tightening then begins at a moderate Hamming bound and may spend the entire rlimit before finding an exact or near-exact theory.

This is not a grammar, operator, latent-partition, or benchmark failure. It is entirely a consequence of the preregistered Hamming-bound order.

## Minimal proposed clarification

If the referee considers the current implementation inconsistent with the intended feasible-first authorization, we request permission to replace **Phase 1 ordering only** with the following deterministic sequence, leaving every other frozen element unchanged:

1. Phase 0 remains unchanged and establishes the legal anytime fallback.
2. The first tightening query is always `E <= 0`, with `N <= N_max`, `D <= max_depth`, and no canonical restriction.
3. If `E <= 0` is feasible, the exact-fit candidate becomes the incumbent and Hamming minimization is complete.
4. If `E <= 0` is proven UNSAT, search the remaining integer interval `[1, E(initial incumbent)]` by the already-frozen deterministic binary rule.
5. If the `E <= 0` query or any later query returns `unknown`/exhausts rlimit, return the existing full-O-verified incumbent immediately.
6. Node, depth, and canonical tightening remain exactly as preregistered.

This rule introduces no operator ordering, structural template, grammar weighting, target-specific condition, corpus-derived parameter, or hidden-world information. The bound `0` is the mathematical lower bound of the already-frozen Hamming objective and is identical for every problem instance.

The rationale is that the qualification corpus is generated from legal Theory ASTs without qualification noise, so an exact-fit solution exists by construction; attempting the mathematical optimum directly without imposing any structural minimization is the cleanest way to obtain a scientifically useful incumbent. On noisy runtime observations, an UNSAT proof falls through to the same deterministic Hamming search already frozen.

## Why we stopped

We did **not** make this change unilaterally because the referee called the feasible-first correction the "absolute final algorithmic adjustment" and required the exact Hamming-bound order to be preregistered before implementation. Changing that order after observing a synthetic failure would otherwise violate the freeze.

## Requested ruling

Please choose one:

### A. CLARIFY / AUTHORIZE PHASE-1 EXACT-FIRST ORDER

Treat the proposed `E<=0` first query as the intended interpretation of the already-authorized feasible-first correction. We may amend the schedule freeze, implement that single ordering correction, rerun only the independent synthetic suite, and, if green, freeze the code and execute the one-shot qualification.

### B. FREEZE CURRENT IMPLEMENTATION AND EXECUTE QUALIFICATION

The current literal schedule is methodologically acceptable despite the synthetic failures. We must freeze it and consume the one-shot qualification as-is.

### C. TERMINATE TOOL-ASSISTED V0

The absolute-final-adjustment condition prohibits any further Hamming-order correction, and knowingly executing the one-shot with the current failing synthetic implementation is unacceptable. Tool-Assisted V0 therefore terminates without qualification exposure.

Benchmark execution remains prohibited under every option.
