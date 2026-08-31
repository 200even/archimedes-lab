# Archimedes V0 — Synthesizer Qualification Result Checkpoint

**Requested ruling:** AUTHORIZE SYNTHESIZER REVISION / HOLD / ABANDON TOOL-ASSISTED V0  
**Current authorization:** Selection plan accepted; concrete synthesizer implementation and benchmark-independent qualification authorized.  
**Benchmark status:** No causal or Null Archimedes benchmark world has been exposed to any language model.

## 1. Frozen qualification rule

Before qualification execution, `QUALIFICATION_PLAN.json` froze:

- corpus size: 1,000 canonical ASTs;
- corpus digest: `e5a643f5b7bf4c9c69297108a9ad4fa29569ca52152de40a2449b98e9c998400`;
- grammar depth: <= 5;
- synthesizer depth: <= 6;
- endpoint: complete 8x8 observational equivalence;
- recovery threshold: >= 0.95;
- ceiling ladder: `256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536`;
- selection rule: choose the smallest preregistered ceiling reaching >=0.95 recovery; if none qualifies through 65,536, do not extend or modify the ladder without a new referee ruling.

The qualification corpus is independent of the Hidden World generator and contains no entity partition problem, no A/B transfer structure, no Null condition, and no Archimedes benchmark seeds.

## 2. Observed qualification result

The complete frozen result was:

| semantic ceiling | recovered / 1000 | recovery rate |
| ---: | ---: | ---: |
| 256 | 546 | 0.546 |
| 512 | 546 | 0.546 |
| 1,024 | 546 | 0.546 |
| 2,048 | 689 | 0.689 |
| 4,096 | 772 | 0.772 |
| 8,192 | 808 | 0.808 |
| 16,384 | 815 | 0.815 |
| 32,768 | 821 | 0.821 |
| 65,536 | 826 | 0.826 |

No preregistered ceiling reached the required 0.95 recovery threshold.

Therefore the mechanically selected result is:

`selected_search_ceiling = null`

and

`status = NO_CEILING_QUALIFIED`.

The exact machine-readable result is committed in `QUALIFICATION_RESULT.json`. The GitHub Actions qualification run is `33358350725`.

## 3. Interpretation

We do **not** propose silently lowering the 95% threshold, extending the ceiling ladder, changing the search algorithm, or using Archimedes benchmark performance to choose a repair.

The qualification failure is an engineering failure of `EnumerativeSynthesizer V0.1` under its preregistered competence criterion. It is not evidence for or against the Archimedes scientific hypothesis because no benchmark world has been exposed.

The recovery curve also appears to plateau substantially below the target: increasing the semantic ceiling from 16,384 to 65,536 improves recovery only from 0.815 to 0.826. This suggests that merely extending the existing ceiling is unlikely to be a principled repair; the current bounded beam/enumeration strategy may be structurally incomplete for a uniform depth-5 grammar.

## 4. Methodological issue now requiring referee authorization

The accepted selection protocol deliberately separated two questions:

1. Is the synthesis tool competent enough to perform deterministic law fitting conditional on an LLM-supplied partition?
2. Does Archimedes discover a useful partition and transfer it across paradigms?

Qualification answered question 1 negatively for the current implementation.

We see three epistemically defensible paths, but do not choose among them without a ruling.

### Option A — authorize one benchmark-independent synthesizer redesign

Permit a new synthesizer version, e.g. `EnumerativeSynthesizer V0.2`, designed solely to improve completeness on the same already-frozen uniform qualification corpus/criterion.

To avoid an open-ended tuning loop, we propose that such authorization, if granted, be constrained in advance. Possible constraints:

- exactly one algorithmic redesign round;
- qualification corpus and 95% endpoint remain unchanged;
- no Archimedes world exposure;
- no changes to the Theory AST grammar;
- no changes to latent-partition restrictions;
- no lowering of the threshold;
- no new corpus generation;
- redesign must be deterministic and identically available to Full and Flat;
- submit the proposed V0.2 algorithm to the referee **before** rerunning the qualification corpus.

### Option B — accept a weaker qualified synthesizer

Freeze the best achieved V0.1 ceiling despite 82.6% qualification recovery and proceed, while treating synthesis failure as part of both arms' shared resource limitation.

We regard this as methodologically weaker because it contradicts the preregistered 95% engineering-competence criterion and could cause false negatives unrelated to the epistemic architecture.

### Option C — abandon deterministic synthesis assistance for V0

Remove the synthesizer from both Full and Flat and require the model itself to emit complete executable programs under matched compute.

This preserves baseline parity but materially changes the previously accepted attribution boundary between concept formation and algebraic law fitting.

## 5. Our preferred methodological path

We recommend **Option A only if the referee explicitly authorizes a single preregistered redesign round before implementation**.

We do not recommend extending the current search ceiling: the observed plateau makes that look like post-hoc brute-force escalation rather than a principled competence fix.

A V0.2 redesign should target algorithmic completeness/coverage of the public grammar, not the observed operator frequencies of the failed corpus, and should still be forbidden from searching entity partitions.

We will not implement such a redesign until the referee rules on whether a post-qualification engineering redesign is acceptable and, if so, what constraints must be frozen before code changes.

## Requested ruling

Please return one of:

### AUTHORIZE SYNTHESIZER REVISION

The failed benchmark-independent engineering qualification may be followed by one tightly preregistered V0.2 synthesizer redesign. Specify any mandatory constraints that must be frozen before implementation or requalification.

### HOLD

The qualification failure requires a different resolution before further implementation. Specify the exact required path.

### ABANDON TOOL-ASSISTED V0

A post-qualification synthesizer redesign would introduce unacceptable researcher degrees of freedom; deterministic synthesis assistance should be removed or V0 should be reformulated.

No ruling here should authorize causal or Null benchmark exposure. Benchmark execution remains prohibited pending the final pre-exposure freeze.
