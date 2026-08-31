# Archimedes V0.1.2 — Referee Checkpoint

**Status:** STOP GATE before any Conjecturer prompt, Critic prompt, or comparative model experiment.

**Current implementation state:** Hidden World generator, solvability/nontriviality validation, condition blinding, deterministic Theory AST evaluator, Experiment Broker, sealed transfer evaluation, abstention path, tests, and CI are implemented. No Conjecturer or Critic prompt has been written.

## Purpose of this checkpoint

Implementation exposed two construct-validity questions that were not sufficiently explicit in the V0 authorization. We are therefore stopping before model exposure and requesting a referee ruling rather than silently choosing a more favorable interpretation after seeing model behavior.

## Safeguards implemented since authorization

### 1. Condition blinding — amendment 0.1.1

The original development bundle encoded causal/Null condition and generator seed in agent-visible metadata. Before any model experiment, this was removed:

- agent-visible `world_kind` is always `experimental`;
- benchmark `world_id` is opaque and unrelated to condition or seed;
- true condition and seed are trusted-side only;
- agent-visible filenames may not encode condition or seed.

This closes an otherwise fatal Null-World leakage path.

### 2. Theory-grounded transfer — amendment 0.1.2

The initial Broker allowed an agent to submit transfer predictions after committing a Theory AST. That would permit the transfer score to reflect an ad hoc guesser rather than the stated explanatory concept.

V0.1.2 now requires:

1. A committed A theory must fit the 64 visible A observations at >= 0.90 exact accuracy.
2. The latent assignments and A program are then immutable.
3. A final B program must fit the 32 visible B-calibration observations at >= 0.90 exact accuracy.
4. A and B must use nonempty, disjoint nontrivial operator signatures; final categorical permutation wrappers are ignored for this criterion.
5. Both explanatory programs must obey the already frozen maximum AST depth of 6.
6. The Broker itself evaluates the committed B Theory AST with the frozen A latent assignments and commits all 32 transfer predictions before requesting any sealed transfer measurements.
7. The agent therefore cannot bypass its declared theory with independent transfer guesses.

### 3. Condition-blind abstention

A meaningful Null-World false-positive test requires the system to be able to conclude that no explanatory concept is justified.

After exactly 64 A interventions the Broker now permits an irreversible `no_concept` declaration in every condition. This closes the run and forfeits all remaining B budget.

- On a causal world, abstention is a D4 failure.
- On a Null world, abstention is the intended true-negative behavior.
- A Null-world positive is operationally a Broker-accepted A theory clearing the >= 0.90 visible-fit gate and advancing to B calibration.

This path is condition blind.

## Current deterministic execution path

```text
64 A interventions
       |
       +--> NO_CONCEPT --> run closes
       |
       v
A Theory AST
       |
 deterministic fit + structure gate
       |
 freeze latent assignments + A program
       |
       v
32 B calibration interventions
       |
       v
B Theory AST
       |
 deterministic fit + operator-diversity gate
       |
       v
Broker derives and commits 32 predictions
from the Theory AST and frozen latent
       |
       v
32 sealed B-transfer measurements
       |
       v
D4 deterministic score
```

No transfer outcome is available to the operating agent before closure.

## Verification status

The repository now has continuous integration on Python 3.12. The corrected CI run installs the package and executes the full pytest suite successfully. The current tests cover generator invariants, condition blinding, Broker phase/budget enforcement, immutable latent identity, deterministic theory evaluation, operator diversity, complexity limits, the no-concept path, transfer sealing, and the full oracle-valid D4 path.

## Unresolved construct-validity issue A: fixed latent cardinality

The current Theory AST declares the candidate latent variable as a categorical variable with **cardinality 8**, and the Broker requires the assignments to use all eight states.

That means the operating system is not being asked to invent the abstract proposition:

> “There exists some reusable latent partition of these entities.”

It is being asked a narrower question:

> “Can I infer the entity assignments for an eight-state latent categorical variable and then reuse that partition across a structurally different interaction?”

The hidden world also has eight true q states, so the cardinality scaffold is correct by construction.

This is not outcome leakage, but it is representational scaffolding. We believe the current experiment can still support a D4 claim about **latent partition discovery and frozen cross-paradigm explanatory reuse**, but it may be too strong to call this unrestricted concept invention.

### Requested ruling A

Choose one:

**A1 — ACCEPT WITH NARROWED CLAIM.** Keep the frozen V0 generator and cardinality-8 Theory AST. Explicitly define the V0 construct as *latent partition discovery and explanatory reuse*, not unconstrained concept invention.

**A2 — REVISE BEFORE MODEL EXPOSURE.** Make latent cardinality unknown to the agent and require it to select/infer cardinality from a preregistered range. This would require a new freeze version before any model run.

**A3 — OTHER.** Specify a stronger operationalization that preserves the current V0's comparability while avoiding cardinality leakage.

## Unresolved construct-validity issue B: Theory DSL mirrors hidden operator vocabulary

The Theory AST currently permits the same primitive operator vocabulary used by the hidden generator:

- `add_mod`
- `mul_mod`
- `xor`
- `rotl`
- `permute`

The agent will not have access to generator source, hidden programs, validation reports, seeds, or GitHub during an experimental run. Nevertheless, the schema itself tells the agent that the true explanation is expressible using a small vocabulary containing exactly the relevant operator families.

This creates another form of representational scaffolding. It is analogous to giving a scientist a box containing only the instruments needed for the correct theory.

### Requested ruling B

Choose one:

**B1 — ACCEPT WITH NARROWED CLAIM.** Treat the DSL as the preregistered hypothesis language. V0 tests discovery *within a supplied representational language* plus cross-paradigm reuse.

**B2 — ADD DISTRACTOR OPERATORS.** Freeze a strict superset DSL containing irrelevant operator families, so the agent must identify both the latent partition and the useful operator family. The hidden generator remains unchanged, but the hypothesis language changes before model exposure.

**B3 — STRONGER REVISION.** Decouple the submitted theory representation from the hidden generator more substantially, for example through bounded generic program synthesis. This would likely constitute a new V0 preregistration version.

## Our proposed interpretation

We recommend **A2 + B2** if the goal is to preserve the stronger phrase “concept discovery.” Neither requires changing the hidden causal worlds themselves:

- q may remain eight-state in ground truth, while the agent is allowed/prerequired to infer a cardinality from a frozen range;
- the hidden programs may remain exactly as authorized, while the public Theory DSL becomes a strict superset with preregistered distractor operators.

If minimizing experimental degrees of freedom and reaching a clean first result is more important, **A1 + B1** is also methodologically defensible, but the claim must then be narrowed to:

> Given a supplied finite hypothesis language and latent-variable type, can an autonomous epistemic architecture infer a reusable latent partition in Paradigm A and preserve it to achieve zero-shot interventional transfer in a structurally distinct Paradigm B better than Flat LLM + synthesis?

That is still a nontrivial and falsifiable V0 result. It is simply not unrestricted concept invention.

## Additional authorization requested

After rulings A and B, please state whether we may proceed to the next implementation stage:

1. build the **Critic qualification harness** with deliberately injected structurally flawed theories and the binding three-failure kill criterion;
2. build a **stateless model adapter** that enforces separate Conjecturer/Critic inference calls and AST-only communication;
3. freeze the **cross-world sample size, statistical test, effect criterion, and high-confidence Null declaration rule**;
4. only then write the first operating prompts and run pilot worlds.

We specifically do **not** request authorization to run comparative experiments yet.

## Requested decision format

Please return:

- **RULING A:** A1 / A2 / A3
- **RULING B:** B1 / B2 / B3
- **V0.1.2 safeguards:** ACCEPT / REVISE
- **NEXT IMPLEMENTATION STAGE:** AUTHORIZE / HOLD
- Mandatory changes, if any.
