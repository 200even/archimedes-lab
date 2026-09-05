# Referee Decision — V1.1 Broker-Assigned-ID Implementation Authorized

**Decision:** A. AUTHORIZE V1.1 BROKER-ASSIGNED-ID IMPLEMENTATION AND NEW CRITIC QUALIFICATION

**Scope:** Authorizes only the V1.1 bookkeeping-ID interface correction, synthetic CI, source/config freeze, and one fresh three-cycle Critic qualification using the already frozen `CQ-1`, `CQ-2`, and `CQ-3` fixtures. It does **not** authorize causal or Null benchmark exposure.

## Binding interpretation

1. `experiment_id` is non-semantic bookkeeping and is removed from the model-facing Critic output schema.
2. The trusted side assigns deterministic canonical IDs from cycle/round index and array position only.
3. The trusted transformation may add only `experiment_id`; it may not repair, reorder, drop, merge, deduplicate, or otherwise alter any scientifically meaningful field.
4. The existing V1 `COMPLETED_FAIL` record remains immutable and is not rescored.
5. V1.1 is a new protocol version and qualification, not a retry of V1.
6. The three existing Critic qualification fixtures and contradiction targets remain frozen.
7. V1.1 passes if at least one cycle includes its preregistered contradiction-revealing `(entity_id, action_value)` pair. Three misses permanently fail the V1.1 Critic safeguard.
8. Provider/transport failures retain the accepted zero-retry infrastructure-abort treatment.

## Required sequence

1. Implement the model-facing schema without `experiment_id`, with `additionalProperties: false`.
2. Implement deterministic canonical ID injection.
3. Verify CI invariants A-H from `REFEREE_CHECKPOINT_V11_BROKER_ASSIGNED_IDS.md` using synthetic/fake-provider data only.
4. Freeze exact V1.1 source/config hashes.
5. Create a fresh one-shot V1.1 qualification trigger.
6. Execute the three frozen fixtures exactly once.
7. Package result and provider metadata and return to the referee.

## Continuing prohibition

No causal or Null benchmark world may be generated for, exposed to, or accessed by any language model during this procedure. Benchmark execution remains locked pending a separate explicit referee ruling.
