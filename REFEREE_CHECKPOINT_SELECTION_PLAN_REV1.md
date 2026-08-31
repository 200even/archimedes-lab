# Archimedes V0 — Model/Synthesizer Selection Plan Revision 1

**Requested ruling:** ACCEPT SELECTION PLAN / HOLD — REVISE  
**Current ruling:** HOLD — REVISE  
**Benchmark status:** No causal or Null benchmark world has been exposed to a model.

This revision addresses only the two mandatory issues in the latest HOLD: qualification-distribution leakage and Flat-baseline compute mismatch. We have not implemented the concrete synthesizer and have not enabled benchmark execution.

## 1. Uniform synthesizer qualification

We accept the requirement that synthesizer engineering qualification must not inherit Hidden World priors.

The 1,000 qualification expressions will be sampled IID from a dedicated finite grammar `G_Q` that is independent of the Hidden World generator.

`G_Q` fixes otherwise open choices so uniformity is mathematically defined:

- variables exactly `{q, a}`;
- constants exactly `0..7`;
- exactly the public Theory AST operator vocabulary, including distractors;
- all schema-valid finite rotation shifts;
- all `8!` schema-valid output permutations;
- maximum syntax-tree depth 5;
- no entity assignments, A/B transfer structure, generator templates, free-form identifiers, or benchmark metadata.

**Uniform means uniform over complete canonical syntax trees of depth <= 5.** Each distinct canonical AST receives equal probability. The sampler will use exact dynamic-programming subtree counts / equivalent rank-unrank weighting. It will not sample an operator uniformly and recurse, because that would not be uniform over complete ASTs.

The qualification sampler is forbidden from importing the Hidden World generator or any generator template/weight data. Its RNG seed and resulting 1,000-AST corpus digest will be frozen before the qualification run.

Qualification contains no latent-partition search. A fixed variable mapping is supplied. The endpoint is only whether the deterministic synthesizer recovers an observationally equivalent program.

The search ceiling will be the **smallest** tested ceiling giving >=95% recovery over the frozen 1,000-expression corpus. No Archimedes world or D4 outcome may participate in that selection.

### Requested ruling A

Does this exact finite-grammar/uniform-tree definition close the distribution-leakage vulnerability?

## 2. Compute-matched Flat baseline

We also accept that the previous Flat baseline was compute-underpowered. During this revision we found and corrected a related arithmetic documentation error: Full has **12** Conjecturer calls plus 10 Critic calls on a completed world, not 11 + 10.

### Full resource envelope

Ten research rounds each contain:

- Conjecturer: one fresh call, max 4096 output tokens;
- Critic: one fresh call, max 2048 output tokens.

There are also two Conjecturer commit calls, each max 4096.

Therefore Full receives:

- 22 calls total;
- maximum output-token envelope = `12*4096 + 10*2048 = 69,632`.

### Flat resource envelope

Each of the same ten research rounds will contain two fresh calls under the **same Flat role/system prompt**:

1. **Flat Generate**: max 4096 output tokens; emits a `CandidateSet`.
2. **Flat Select**: max 2048 output tokens; receives only the normalized `CandidateSet` plus the same current visible data and emits the intervention batch.

Flat Select does not receive the Critic prompt, an adversarial/falsification instruction, Critic history, or raw Generate reasoning. It is a same-role stateless self-refinement call.

Flat also receives two 4096-token commit calls.

Therefore Flat receives:

- 22 calls total;
- maximum output-token envelope = `10*4096 + 10*2048 + 2*4096 = 69,632`.

Generate/Conjecturer, Select/Critic, and commit slots are one-for-one matched in call count and output-token ceiling. All roles use the same model and `thinking_level=high`.

The architectural contrast is thus:

- **Full:** proposal followed by a separately prompted, causally isolated adversarial Critic.
- **Flat:** proposal followed by same-role non-adversarial self-refinement.

It is no longer a contrast in available call count or maximum output-token capacity.

## 3. Dynamic-thinking compute audit

The proposed stable model remains `gemini-3.7-flash`. Its `thinking_level=high` controls a relative reasoning allowance rather than an exact thought-token count, so exact realized reasoning tokens cannot be prospectively forced equal even with identical call/configuration envelopes.

The trusted provider adapter will therefore log per-call provider usage metadata for both arms: input tokens, output tokens, thought tokens, total tokens, latency, and returned model/version metadata. None of these values is shown to either operating arm.

We propose an additional aggregate validity diagnostic across the 100 paired causal worlds:

`R_compute = total_provider_tokens_Full / total_provider_tokens_Flat`.

Proposed acceptable band: `0.95 <= R_compute <= 1.05`.

If Full lies above 1.05, a nominal performance win cannot be interpreted as evidence for the epistemic architecture because greater realized compute remains a plausible explanation. No post-hoc top-up calls or outcome-dependent reruns are permitted. If Flat consumes materially more compute, this is reported as a conservative advantage to Flat.

### Requested ruling B

Is the exact 22-call / 69,632-token matched envelope sufficient? Given the provider's dynamic thinking, should the proposed 5% aggregate realized-token validity band also be binding, should it be different, or should matching the prospective envelope alone define compute parity?

## 4. Model selection remains a priori

We retain the a-priori model choice:

- Google Gemini Developer API;
- stable `gemini-3.7-flash` identifier;
- Gemini Interactions API;
- `thinking_level=high` for every Full and Flat model call;
- structured output required;
- built-in tools/search/code execution/file search/URL context disabled;
- no persistent interaction continuation.

No multi-model tournament is permitted. Temperature/top-p/top-k are not being tuned; they are omitted for this model/API rather than used as selection parameters.

## 5. What has not happened

- The concrete enumerative synthesizer has not been implemented.
- No qualification corpus has been generated.
- No search ceiling has been selected.
- The Flat orchestrator has not yet been changed to the proposed two-slot schedule; implementation awaits approval of this design.
- No benchmark world has been supplied to an LLM.

## Requested ruling

### ACCEPT SELECTION PLAN

The strictly uniform qualification distribution and compute-matched Flat design sufficiently close the two mandatory vulnerabilities. We may implement the synthesizer qualification machinery and matched Flat schedule, but benchmark exposure remains prohibited pending the final pre-exposure freeze.

### HOLD — REVISE

Specify the remaining methodological defect before implementation continues.

We specifically request an explicit ruling on (A) the uniform canonical-AST sampler definition and (B) whether prospective compute-envelope parity plus provider usage auditing is sufficient for a dynamic-thinking model.