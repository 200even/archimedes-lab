# Archimedes V1 — Provider Adapter Replacement Amendment

**Status:** FROZEN BEFORE REPLACEMENT CRITIC QUALIFICATION

This amendment is limited to the infrastructure defect observed in workflow run `33781365337`. It does not alter any scientific fixture, prompt, intervention-selection rule, model, seed, output schema, timeout, retry policy, or benchmark authorization.

## Narrow amendment

For the frozen Gemini Interactions request, `store=false` is mandatory. When the provider returns an otherwise valid completed interaction but omits `id` or returns `id: null`, the adapter records:

`interaction_id = null`

and continues through the trusted usage/hash ledger and normative V1 response validator.

A non-null `id` must still be a nonempty string. Any malformed non-null ID remains a provider-protocol failure.

## Invariants retained

The adapter still requires all of the following before any model output can be scientifically evaluated:

1. one HTTP POST only, with no automatic retry;
2. HTTP 2xx;
3. JSON response root;
4. `status == "completed"`;
5. `model == "gemini-3.7-flash"`;
6. a valid `steps` array;
7. no unexpected tool/function/action step;
8. model-output text present;
9. model-output text parses as one JSON object;
10. downstream normative Pydantic/Broker validation.

The request remains stateless with `store=false`, `stream=false`, `background=false`, no tools, no previous interaction, seed `20260902`, `thinking_level=high`, `thinking_summaries=none`, and a 300-second single-attempt timeout.

## Audit behavior

`GeminiUsageRecord.interaction_id` becomes nullable. Request SHA-256, response-text SHA-256, returned model, provider status, role/task/round metadata, slot token cap, and all provider-reported usage counts are recorded even when `interaction_id` is null.

The prior aborted run `33781365337` remains permanently recorded as an unrecovered infrastructure event. It is not erased, rescored, or merged into the replacement safeguard.

## Replacement rule

The replacement execution must run exactly the unchanged CQ-1, CQ-2, and CQ-3 fixtures once under a dedicated replacement trigger. No manual workflow rerun substitutes for that trigger.

## Benchmark firewall

No causal or Null benchmark execution is authorized by this amendment.
