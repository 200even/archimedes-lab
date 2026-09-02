# Referee Checkpoint — V0.2 Exact-First Final Synthetic Validation Failure

**Status:** STOPPED BEFORE QUALIFICATION — REFEREE RULING REQUIRED

## Authorization implemented

The referee authorized the final deterministic search sequence:

`Fallback -> E <= 0 -> binary tightening of remaining Hamming interval -> structural tightening`

with the initial `E <= 0` query unconstrained by node-count or depth minimization beyond the frozen maximum grammar skeleton.

The schedule was amended **before** the implementation change, preserving the requested preregistration order.

Relevant commits:

- referee decision record: `374b066d05fe8109d8b879596d066224df2360ae`
- amended schedule freeze: `ff70bcb64ed2a81df39cca81599de3e8a487186e`
- exact-first implementation: `b7a5618be32ac53718aa56f636985d75dffbeb58`
- qualification runner provenance correction: `c816489a8a40d25a7f693edfce4f849d8a06150e`

The qualification runner correction does not change synthesis. It ensures the future one-shot, if authorized, imports the final bound implementation rather than the pre-hardening base class and hashes all runtime synthesis modules contributing to the bound engine.

## Synthetic validation result

GitHub Actions CI run:

`https://github.com/200even/archimedes-lab/actions/runs/33646039614`

Result:

- **40 passed**
- **3 failed**
- qualification trigger not created
- qualification corpus not executed
- no causal or Null benchmark world exposed

### Passed improvement

The exact-first order fixed the earlier basic-law regression. The independent `add_mod(q,a)` synthetic fixture now recovers an exact program under its frozen 5M synthetic-test resource allowance.

### Failure 1 — nested permutation, depth 4

The independent synthetic fixture

`permute(xor(rotl(q,1), a), mapping=[3,1,7,0,5,2,6,4])`

still does not return an exact candidate under the frozen 50M cumulative rlimit.

The anytime policy now correctly preserves and returns a full-`O`-verified legal fallback candidate when the exact-first search cannot complete, but the returned fallback has exact accuracy **0.125**, not 1.0.

### Failure 2 — same fixture in qualification-depth skeleton

The identical independent synthetic target inside the depth-5 skeleton also returns a verified fallback with exact accuracy **0.125** rather than an exact solution under the same 50M cumulative rlimit.

Thus the authorized exact-first reorder does not make the solver competent on the pre-existing hard synthetic fixture.

### Failure 3 — deterministic replay

For the independent `xor(q,a)` replay fixture, both invocations recover the same canonical AST and truth table, but the solver-control trace is not mechanically identical:

- first invocation: **12 SAT checks**
- second invocation: **13 SAT checks**

This violates the existing synthetic assertion that the frozen deterministic procedure produce the same SAT-check count on replay.

## Interpretation

The exact-first clarification improved the search schedule in the intended direction, but the full independent synthetic suite still does not pass.

The evidence now supports a narrower diagnosis than before:

1. exact-fit-first is sufficient for simple two-variable laws;
2. the legal depth-4 nested permutation remains beyond the practical capability of this bounded SMT/CEGIS implementation under the frozen 50M cumulative resource ceiling;
3. invocation-local contexts are not sufficient to make the complete solver-control trace mechanically identical under the new exact-first sequence, even though the recovered simple program itself is deterministic;
4. the qualification precondition explicitly required by the referee — **independent synthetic suite passes** — is not satisfied.

No qualification-derived information exists. This diagnosis is based only on the same independent synthetic fixtures used throughout prequalification engineering.

## Blinding / one-shot status

`V02_QUALIFICATION_TRIGGER.txt` does **not** exist.

Therefore:

- the frozen 1,000-AST qualification corpus has not been executed by V0.2;
- the one-shot qualification has not been consumed;
- no per-item qualification failure information exists;
- no Archimedes causal benchmark world has been exposed;
- no Null benchmark world has been exposed.

## Authorization boundary

The previous ruling described the exact-first change as the final schedule clarification and required:

> Once the independent synthetic suite passes and the code hash is frozen, execute the 1,000-AST qualification corpus exactly once.

That antecedent is false: the synthetic suite does not pass.

Accordingly, I have **not**:

- changed the solver encoding again;
- changed the rlimit;
- weakened or removed the failing synthetic fixture;
- relaxed deterministic replay assertions;
- altered the grammar;
- added operator-specific heuristics;
- created the qualification trigger;
- run any qualification shard.

## Requested ruling

Because the authorized algorithmic/schedule adjustment budget appears exhausted, please rule explicitly on the scientifically correct terminal action.

### Option A — TERMINATE TOOL-ASSISTED V0

Treat failure of the required independent synthetic suite after the final authorized adjustment as terminal. Record Tool-Assisted V0 as abandoned without consuming the qualification one-shot.

This is the conservative interpretation of the existing authorization.

### Option B — AUTHORIZE QUALIFICATION DESPITE SYNTHETIC FAILURE

Override the prior synthetic-pass precondition and explicitly authorize the one-shot 1,000-AST qualification with the implementation as frozen now.

This would knowingly enter qualification with a solver that fails a legal independent depth-4 synthetic target, so it should be authorized only if the referee judges that fixture stricter than the scientific qualification requirement.

### Option C — EXPLICITLY AUTHORIZE A NEW ENGINEERING CHANGE

Only if the referee determines that the remaining behavior is an implementation defect rather than exhaustion of the authorized redesign, specify the exact additional correction allowed. No such change will be made without a new explicit authorization.

## Recommendation

**Option A — TERMINATE TOOL-ASSISTED V0.**

The project has now given the deterministic synthesis tool multiple preregistered, benchmark-blind opportunities to demonstrate competence. The final authorized schedule improves simple exact fitting but still fails the required independent synthetic suite under the frozen resource ceiling. Continuing to alter the solver would create precisely the open-ended engineering/tuning loop the one-shot rule was designed to prevent.

This conclusion concerns only **Tool-Assisted V0**. It does not constitute evidence for or against the Archimedes D4 epistemic-architecture hypothesis, because no Archimedes benchmark world has yet been exposed to the operating language model.
