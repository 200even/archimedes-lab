# Archimedes V0 — Hidden World Lab

Archimedes V0 is a preregistered experiment in whether an AI system can discover a reusable explanatory abstraction and transfer it across a structurally different causal paradigm.

**Current status: V0.1.3 safeguards accepted; agent-layer implementation authorized; benchmark exposure still prohibited.** The hidden-world generator, trusted Broker, deterministic Theory AST evaluator, cardinality safeguards, Z3 structural-isomorphism checks, stateless agent interfaces, deterministic orchestration, baseline interfaces, and functional-minimality diagnostic now exist.

No causal or Null benchmark world has been supplied to a Conjecturer or Critic. See [`PRE_REGISTRATION_FREEZE.md`](PRE_REGISTRATION_FREEZE.md) for the binding world/Broker protocol, [`REFEREE_DECISION_V0_1_3.md`](REFEREE_DECISION_V0_1_3.md) for the authorization scope, and [`PRE_EXPOSURE_FREEZE_DRAFT.md`](PRE_EXPOSURE_FREEZE_DRAFT.md) for the still-incomplete pre-exposure protocol.

## Trusted boundary

Each generated world has three artifact classes:

- `*.public.json` — condition-blind metadata safe for the operating side.
- `*.hidden.json` — sealed ground truth; never expose to the model process.
- `*.validation.json` — trusted solvability/nontriviality report; also sealed during a run.

`world.py`, the generator, hidden specs, seeds, validation reports, and trusted ledger must remain outside the model environment.

## Hidden worlds

A causal world has 16 opaque entities. Its reusable hidden quantity has an undisclosed cardinality `k ∈ {2,3,4}`. The operating system is not told k.

- Paradigm A is generated from a modular-arithmetic family.
- Paradigm B is generated from a bitwise family.
- Both emit opaque values in `{0,...,7}`.
- Admitted A/B worlds must pass a Z3 non-isomorphism check under arbitrary relabeling of latent, action, and output symbols.

Null worlds expose the identical public interface but contain no causal program or latent quantity.

## Anti-memorization safeguard

Candidate latent cardinality is inferred but hard-capped at:

`k_max = floor(sqrt(16)) = 4`.

Every declared state must be used by at least two entities. This makes a one-state-per-entity lookup table schema-invalid.

If an A theory is accepted, the Broker freezes its latent domain, geometry, cardinality, assignments, and A program before any B data is exposed.

## Hypothesis language

The Theory AST includes the useful finite-domain primitives plus same-type distractors.

Useful generator-capable operators include modular arithmetic, XOR/rotation, and permutation. Distractors include bitwise AND/OR, min/max, absolute difference, and equality-mask operations.

All operators use the same finite 3-bit type, so distractors cannot be rejected merely by spotting a foreign numeric domain.

## Rejection-sampling firewall

V0.1.3 charges theory evaluation against the same 128-unit resource budget used by experiments:

- 60 A-discovery interventions
- 4 units for one A-theory gate
- 28 B-calibration interventions
- 4 units for one B-theory gate
- 32 sealed B-transfer interventions

A gate is attempted **once**. Its budget is charged before parsing or scoring. Any malformed, structurally invalid, or sub-90%-fit theory closes the world immediately. There is no resubmission path.

A condition-blind `no_concept` abstention remains available after the 60 A interventions, but only before attempting the A gate.

## Agent layer

The authorized implementation adds:

- `agent_interfaces.py` — provider-neutral stateless JSON interfaces for Conjecturer, Critic, and Flat baseline roles;
- `neutral.py` — canonical AST/observation projection so raw prose and role history never cross boundaries;
- `orchestrator.py` — deterministic 60-observation A and 28-observation B schedules for Full and Flat arms;
- `synthesis.py` — a shared visible-data-only synthesis interface; the concrete comparative implementation is still unfrozen;
- `diagnostics.py` — functional-minimality analysis of accepted A representations;
- `analysis_plan.py` — world-level paired primary analysis and Null false-positive calculation;
- `prompts/` — exact draft role prompts and their SHA-256 manifest.

Both orchestrators are **blocked by default** and refuse to run unless `execution_authorized=True` is explicitly supplied. Benchmark use of that flag is prohibited until the final pre-exposure freeze is approved.

## Functional minimality

After an accepted A theory, the orchestrator computes each declared label's complete predicted response signature over all eight legal actions. If two labels have identical signatures, the theory is recorded as nonminimal and its effective cardinality is reported. This is a diagnostic, not a new D4 kill gate.

## D4 transfer

After an accepted B theory, all 32 transfer predictions are generated directly from the committed Theory AST before any held-out outcome is requested. Transfer observations stay sealed until closure.

A per-world D4 qualification requires:

- >=90% A visible fit on the one committed theory;
- >=90% B calibration fit on the one committed theory;
- frozen latent representation across A→B;
- nonoverlapping nontrivial A/B operator signatures;
- Z3 proof result `UNSAT` for the preregistered finite isomorphism query;
- >=90% exact accuracy on sealed B transfer.

The research claim is comparative across worlds, not merely passing one world.

## Run trusted-side tests

```bash
python -m archimedes_v0.cli 42 --out worlds
python -m archimedes_v0.cli 43 --out worlds --null
pytest -q
```

These commands exercise trusted deterministic code. They are not authorization to expose generated benchmark worlds to a language model.

## Non-claim

V0 does **not** test D5 ontological revision. The representational family remains deliberately bounded. V0 asks whether an explanatory latent abstraction can be inferred and reused under adversarial controls, not whether the system can invent arbitrary new representational mathematics.

## Remaining pre-exposure blockers

Before any benchmark model call:

1. freeze exact provider/model snapshot and sampling/transport parameters;
2. freeze the concrete shared `CandidateSynthesizer` implementation and invocation schedule;
3. finalize infrastructure-failure handling;
4. hash the completed prompt/config manifest;
5. return the complete pre-exposure protocol to the referee;
6. receive explicit exposure authorization.
