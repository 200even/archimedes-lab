# Archimedes V0 — Broker Hardening Review Request

**Branch:** `broker-hardening`  
**Candidate amendment:** 0.1.2  
**Status:** implemented and tested, but not authorized for model experiments or merge to `main` pending referee ratification.

## Why this review exists

After the authorized Broker was implemented, a construct-validity loophole became apparent before any Conjecturer prompt was written.

The first Broker froze the candidate latent assignments after Paradigm A, but during sealed transfer it still accepted predictions supplied by the agent. A sufficiently capable system could therefore submit a nominal frozen `q`, internally reason with a different representation, and use that private representation to generate successful transfer predictions. The experiment would then award D4 credit without proving that the frozen concept actually participated in the explanation that earned the score.

The `broker-hardening` branch closes that route.

## Proposed 0.1.2 additions

1. **Deterministic theory evaluation.** Theory AST expressions are executable by ordinary code. The Broker, not the agent, generates transfer predictions from the committed B Theory AST and frozen latent assignments.
2. **Prediction commitment before unblinding.** All 32 B-transfer predictions are written to the immutable ledger before the first hidden transfer observation is requested.
3. **A-law freeze.** The Paradigm A program freezes together with `q`; it cannot be rewritten after B data are observed.
4. **Visible explanatory-fit gates.** The A theory must fit the 64 visible A observations at >=0.90 exact accuracy before freeze. The B program must fit the 32 B-calibration observations at >=0.90 before transfer.
5. **Actual concept use.** Both programs must syntactically depend on the frozen latent variable and their intervention variable (`x` or `u`).
6. **Operator diversity.** Ignoring variables, constants, and the final categorical relabeling permutation, the nontrivial operator signatures of A and B must both be nonempty and disjoint.
7. **Bounded constants.** Theory-AST categorical constants are restricted to `D = {0,...,7}`.

No Hidden World causal grammar, intervention budget, transfer success threshold, Null threshold, or D5 restriction is changed.

## Noise calibration for the proposed 0.90 visible-fit gate

Before any model experiment, we simulated **5,000 generated causal worlds** using the frozen 2% measurement corruption rate and the V0 visible-sampling pattern, scoring the true generating theory itself.

- A true-law rejection rate at the proposed `<0.90` gate: **0.0006** (0.06%).
- B true-law rejection rate: **0.0044** (0.44%).
- Minimum observed A accuracy: **0.890625**.
- Minimum observed B accuracy: **0.84375**.

Thus the proposed gate is stringent but can reject the true theory due solely to measurement corruption in approximately 0.5% of B calibrations. We flag this rather than silently tuning the threshold after implementation.

## Requested referee rulings

Please rule separately on the following:

1. **Deterministic transfer:** Ratify or reject the requirement that the Broker derive all transfer predictions directly from the committed Theory AST and frozen latent assignments.
2. **A-law freeze:** Ratify or reject freezing the A program itself before B exposure.
3. **Concept-use constraint:** Ratify or reject requiring both paradigm programs to depend explicitly on the same frozen latent variable and their intervention variable.
4. **Operator-diversity criterion:** Ratify or revise the proposed disjoint nontrivial operator-signature rule.
5. **Visible-fit threshold:** Either ratify `>=0.90` for both A and B, specify a replacement threshold, or specify a noise-aware acceptance test. The choice must be frozen before model experiments.
6. **Merge authorization:** If the above safeguards are acceptable, authorize fast-forward/merge of `broker-hardening` into `main` and progression to the trusted orchestrator/isolation layer. Do **not** authorize a Conjecturer prompt yet unless the process-isolation boundary is also judged sufficient.

## Suggested decisions

- **R1. REJECT HARDENING** — the original authorized Broker is sufficient.
- **R2. REVISE HARDENING** — concept is correct but one or more rules above must change before merge.
- **R3. RATIFY 0.1.2** — merge hardening, then implement trusted process/orchestrator isolation before any model prompt.

The project team recommends **R3 subject to an explicit ruling on the 0.90 visible-fit gate**.
