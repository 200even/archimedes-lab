# Referee Decision — V1 Provider-ID Replacement Qualification

**Decision:** AUTHORIZE NARROW PROVIDER-RECORD REVISION AND REPLACEMENT CRITIC QUALIFICATION

## Authorized adapter change

`archimedes_v0/v1_gemini_backend.py` may treat an omitted or explicit `null` interaction ID as an auditable nullable field only for the frozen stateless request with `store=false`.

The adapter must still require:

- HTTP success;
- `status == "completed"`;
- returned model `gemini-3.7-flash`;
- valid `steps` with no tool/action step;
- JSON-parsable structured model output.

The trusted provider record, request hash, response-text hash, and provider usage fields must be created whether the stateless response contains an interaction ID or not.

## Replacement classification

The prior aborted run `33781365337` is an unrecovered infrastructure event. Its CQ-1 provider transaction was never scientifically scored and CQ-2/CQ-3 were not sent. The authorized next execution is a fresh replacement across the unchanged preregistered fixtures CQ-1, CQ-2, and CQ-3, not an automatic retry of the prior workflow.

## Frozen scientific rule

The fixture file and expected contradiction targets remain unchanged. The Critic safeguard passes if at least one of the three eligible cycles contains its preregistered revealing intervention. Three consecutive misses permanently fail the Critic safeguard.

## Benchmark firewall

No causal or Null benchmark world is authorized. The replacement qualification must return to the referee before any benchmark exposure.
