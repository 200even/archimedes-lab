# Archimedes V1.1 — Referee Checkpoint: Broker-Assigned Experiment IDs

**Status:** HOLD FOR REFEREE RULING — NO PROVIDER OR BENCHMARK EXECUTION AUTHORIZED BY THIS DOCUMENT

## 1. Why this checkpoint exists

V1 completed its authorized replacement Critic qualification with three completed Gemini interactions, but all three cycles were scored as misses because the returned `experiment_id` strings violated the normative regex. The recorded failures were exclusively of the form:

- returned IDs such as `exp_01` ... `exp_10`;
- required pattern `^E-[A-Za-z0-9_-]{1,48}$`.

No other normative validation error was recorded in the three qualification cycles.

Under the frozen V1 rules, those responses were correctly rejected and V1 therefore remains a completed scientific failure. This checkpoint does **not** request retroactive rescoring, normalization, or reinterpretation of the V1 result.

The question for V1.1 is narrower:

> Should a language model be responsible for generating a bookkeeping identifier that carries no scientific content, or should that identifier be assigned deterministically by the trusted Broker after the model has selected the scientifically meaningful intervention?

## 2. Proposed V1.1 interface correction

V1.1 removes `experiment_id` from the **model-facing Critic output schema** and assigns it on the trusted side.

The model remains responsible for every scientifically meaningful intervention field:

- `objective`;
- `paradigm`;
- `entity_id`;
- `action_value`;
- `target_hypothesis_ids`.

The Broker then deterministically injects an identifier based only on trusted call metadata and array position.

For Critic qualification cycle index `r in {0,1,2}` and returned array position `i in {0,...,9}`:

```text
experiment_id = "E-CQ" + str(r + 1) + "-" + two_digit(i + 1)
```

Therefore the only possible qualification IDs are:

```text
CQ-1: E-CQ1-01 ... E-CQ1-10
CQ-2: E-CQ2-01 ... E-CQ2-10
CQ-3: E-CQ3-01 ... E-CQ3-10
```

These identifiers satisfy the existing normative ID pattern and are globally unique across the three qualification cycles.

For later benchmark Critic calls, if benchmark execution is separately authorized, the same rule generalizes mechanically:

```text
experiment_id = "E-R" + two_digit(round_index + 1) + "-" + two_digit(position + 1)
```

No world state, outcome, hidden partition, hypothesis quality, entity identity, or action value enters the identifier function.

## 3. Exact trusted transformation

The V1.1 pipeline is proposed as:

```text
Gemini structured output
        |
        v
V1.1 provider-facing RawExperimentBatch
  - exactly 10 experiments
  - no experiment_id field accepted
  - additionalProperties = false
        |
        v
trusted deterministic ID injection
        |
        v
existing normative AExperimentBatch validation
        |
        v
Critic safeguard scoring
```

The trusted transformation is deliberately non-semantic:

```python
for i, raw in enumerate(raw_batch.experiments):
    full = {
        "experiment_id": canonical_id(round_index, i),
        **raw,
    }
```

The transformation may **only add** `experiment_id`.

It may not:

- alter `entity_id`;
- alter `action_value`;
- alter `paradigm`;
- alter `objective`;
- alter `target_hypothesis_ids`;
- reorder experiments;
- remove duplicate interventions;
- merge experiments;
- add or remove experiments;
- repair any other malformed field;
- inspect the trusted contradiction target;
- inspect any hidden-world data.

If any non-ID field is invalid, the cycle remains a normative miss exactly as in V1.

## 4. Why this does not change the scientific hypothesis

`experiment_id` is not used to determine whether the Critic discovered a contradiction-revealing intervention. The safeguard hit rule depends only on the selected `(entity_id, action_value)` pair matching the preregistered trusted target.

Consequently, trusted ID assignment changes no intervention choice and adds no information about the hidden answer. It removes a serialization burden from the model while leaving the scientific decision variable unchanged.

This is analogous to a laboratory instrument assigning sample numbers after a scientist chooses which samples to collect. The sample number is necessary for bookkeeping but is not itself part of the hypothesis.

## 5. V1 result remains immutable

The existing V1 replacement qualification remains permanently recorded as:

`COMPLETED_FAIL`

with three consecutive misses under the V1 schema.

V1.1 must not:

- recover the historical rejected batches;
- inspect their hidden semantic contents beyond the already-recorded validation errors;
- rewrite `V1_CRITIC_REPLACEMENT_QUALIFICATION_RESULT.json`;
- rescore CQ-1, CQ-2, or CQ-3 from the historical V1 responses;
- call the new run a retry of V1.

Any V1.1 qualification is a **new protocol version and new qualification execution**.

## 6. Frozen V1.1 Critic qualification proposal

If authorized, V1.1 will reuse the same three independent qualification fixtures and the same contradiction targets:

- fixture set: `V1-Critic-Safeguard-1`;
- CQ-1 target unchanged;
- CQ-2 target unchanged;
- CQ-3 target unchanged.

The semantic success rule remains unchanged:

> V1.1 Critic safeguard passes if at least one of the three eligible cycles includes its preregistered contradiction-revealing `(entity_id, action_value)` intervention.

Three misses remain a permanent V1.1 Critic safeguard failure.

A completed provider response with any invalid field **other than the removed model-generated identifier** remains a miss and receives no semantic retry.

Provider/transport failure remains an infrastructure abort under the already accepted zero-retry policy.

## 7. Provider-facing schema rules

The V1.1 Critic provider schema must:

1. omit `experiment_id` entirely from each experiment object;
2. set `additionalProperties: false` for each experiment object, so the model cannot supply or influence an ID through an undeclared field;
3. retain exact batch size 10;
4. retain all currently provider-supported structural constraints for the meaningful fields;
5. continue to pass the post-provider output through trusted Pydantic/Broker validation after deterministic ID injection.

The normative downstream `AExperimentBatch` schema does not need its identifier constraint relaxed. It receives trusted IDs that already satisfy it.

## 8. Required CI before any V1.1 provider call

If implementation is authorized, CI must establish all of the following using only synthetic/fake-provider inputs:

### A. ID determinism

For fixed `(round_index, array position)`, IDs are byte-identical across runs and `PYTHONHASHSEED` values.

### B. ID independence

Changing any scientifically meaningful content while preserving round and position must not change the generated ID.

### C. Semantic preservation

For a valid raw batch, the ordered tuples

```text
(objective, paradigm, entity_id, action_value, target_hypothesis_ids)
```

must be byte-equivalent before and after ID injection.

### D. No repair beyond IDs

Synthetic malformed cases for each meaningful field must remain invalid after the transformation.

### E. No reordering

The output sequence must preserve provider array order exactly.

### F. No target access

The canonicalizer module must not import or read `V1_CRITIC_QUALIFICATION_FIXTURES.json`, trusted target helpers, benchmark generators, world state, or hidden partitions.

### G. Provider schema excludes ID

CI must verify `experiment_id` is absent from the provider-facing Critic schema and that undeclared extra properties are rejected.

### H. Downstream normative compatibility

After injection, the batch must still validate against the existing full `AExperimentBatch` contract including the ID regex and uniqueness requirements.

## 9. Compute and provider controls remain frozen

V1.1 proposes no change to:

- model: `gemini-3.7-flash`;
- API revision: `2026-05-20`;
- decoding seed: `20260902`;
- thinking level: `high`;
- thinking summaries: `none`;
- timeout: `300.0` seconds;
- automatic retries: `0`;
- `store=false`;
- tool prohibition;
- provider-schema projection firewall;
- nullable interaction-ID amendment for stateless responses.

The historical aborted provider-ID run and completed V1 failure remain in the permanent audit ledger.

## 10. Benchmark firewall

This checkpoint does **not** authorize causal or Null benchmark exposure.

If the referee authorizes V1.1 implementation and a new Critic qualification, the sequence must be:

1. implement only the broker-assigned-ID interface correction;
2. add the CI invariants above;
3. freeze exact source/config hashes;
4. verify synthetic CI green;
5. create a new one-shot **V1.1** Critic qualification trigger;
6. execute exactly the three frozen qualification fixtures once;
7. package the result and provider metadata;
8. return to the referee.

Only a subsequent explicit referee ruling may unlock any causal or Null benchmark world.

## 11. Requested referee ruling

Please choose one:

### A. AUTHORIZE V1.1 BROKER-ASSIGNED-ID IMPLEMENTATION AND NEW CRITIC QUALIFICATION

Accept that `experiment_id` is non-semantic bookkeeping, authorize its removal from the model-facing Critic schema and deterministic trusted assignment as specified above, followed by one fresh three-cycle V1.1 Critic qualification after synthetic CI and code freeze.

### B. AUTHORIZE IMPLEMENTATION ONLY

Permit the interface correction and synthetic CI, but require a second checkpoint before any V1.1 provider call.

### C. REJECT V1.1 / RETAIN V1 TERMINATION

Treat exact model-generated experiment-ID compliance as part of the scientific Critic safeguard and do not permit a successor qualification.

## Recommended ruling

**A. AUTHORIZE V1.1 BROKER-ASSIGNED-ID IMPLEMENTATION AND NEW CRITIC QUALIFICATION.**

The proposed change removes a bookkeeping-only serialization variable, does not alter the intervention selected by the model, does not use any hidden answer, preserves every scientifically meaningful validation rule, and leaves the failed V1 record untouched.
