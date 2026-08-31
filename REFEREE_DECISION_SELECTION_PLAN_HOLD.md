# Referee Decision — Model and Synthesizer Selection Plan

**Decision:** HOLD — REVISE

The operational/scientific firewall is accepted in principle, but two methodological vulnerabilities must be corrected before the selection plan is accepted.

## Accepted points

1. **A-priori model selection.** Blindly freezing one stable high-reasoning model is methodologically preferable to a multi-model tournament.
2. **Synthesizer boundary.** The synthesizer may fit laws only after the LLM supplies `k_hat` and entity-to-latent assignments. It may not search or alter latent assignments.
3. **Mechanical model qualification.** JSON compliance, statelessness, timeout behavior, and other purely operational checks do not contaminate the scientific hypothesis.

## Mandatory revision 1 — synthesizer qualification uniformity

The 1,000-AST engineering corpus must not reproduce Hidden World sampling priors. It must be sampled from a strictly uniform distribution over the finite Theory AST qualification grammar up to depth 5, explicitly decoupled from Hidden World generator templates, weights, and structural biases.

## Mandatory revision 2 — compute-matched Flat baseline

The Flat LLM+synthesis baseline must receive inference-compute parity with Archimedes Full. A Full win must not be explainable merely by Full receiving substantially more reasoning-token/model-call capacity. The revised protocol must specify an exact compute-matching mechanism, such as Best-of-N/self-refinement or an equivalent matched reasoning envelope, while preserving the absence of an independently isolated adversarial Critic.

## Authorization boundary

No benchmark exposure is authorized. Submit the corrected uniform qualification rule and compute-matched baseline design for acceptance before implementing the concrete synthesizer or running any benchmark model call.
