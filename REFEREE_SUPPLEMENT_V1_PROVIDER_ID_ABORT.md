# Archimedes V1 — Provider-ID Infrastructure Abort Supplement

**Status:** POST-ABORT DIAGNOSTIC ONLY — NO RETRY OR BENCHMARK EXPOSURE AUTHORIZED

This supplement records a non-provider investigation after the one-shot V1 Critic safeguard execution aborted. It does not alter the frozen scientific protocol and does not authorize another Gemini call.

## 1. Empirical execution facts

The authorized workflow run was `33781365337` at execution commit `4c2e8d8bc10080c8d38952b4b6aa12bbabd5c290`.

The one-shot trigger and frozen authorization validated successfully. The first provider slot was entered. The execution then terminated with:

`V1ProviderError: Gemini completed response omitted interaction id`

The adapter reaches that check only after all of the following have already succeeded:

1. the HTTP response was 2xx;
2. the response body parsed as JSON object;
3. root `status == "completed"`;
4. root `model == "gemini-3.7-flash"`;
5. the response contained a valid `steps` array;
6. the response contained model-output text;
7. that text parsed as a JSON object.

Therefore one provider request was sent and a completed model response was received, but it was rejected at the provider-protocol layer before trusted Critic semantic scoring. No later Critic cycle was sent.

The evidence package correctly classifies the execution as `ABORTED_PROVIDER_INFRASTRUCTURE`. No automatic retry or replacement call occurred. No causal or Null benchmark world was exposed.

## 2. Audit limitation discovered by the abort

`GeminiUsageRecord` is appended only after the interaction-ID validation. Consequently the completed-but-protocol-invalid first response produced no trusted usage record. The committed usage artifact is therefore `[]`, and the result package reports zero *successful recorded provider interactions* even though one provider request was in fact sent.

The raw provider response was not retained. This is consistent with the privacy/minimal-retention intent of the adapter, but it means the missing-ID response cannot now be rescored or used as a scientific Critic result.

No attempt should be made to infer whether CQ-1 selected the revealing intervention.

## 3. Documentation check performed after the abort

A post-abort, non-provider review of the current Google Gemini documentation found:

- the Interactions API reference describes `id` as the unique identifier of an interaction and current examples show a root-level `id`;
- the same generated reference schema labels the `id` field syntactically optional while its prose says `Required. Output only.`;
- Google documents `store=false` as the stateless mode that opts out of storing the interaction for later retrieval.

Relevant Google documentation:

- https://ai.google.dev/api/interactions-api-v1
- https://ai.google.dev/gemini-api/docs/interactions-overview
- https://ai.google.dev/gemini-api/docs/interactions-breaking-changes-may-2026

The documentation therefore does not establish with sufficient certainty whether omission of `id` under `store=false` is a supported response variant, a provider defect, or a transient protocol inconsistency. The actual response body was not retained, so no stronger claim is warranted.

## 4. Scientific consequence

The Critic safeguard has **not passed and has not failed scientifically**. It is unresolved because the authorized execution aborted before any cycle became a trusted scored result.

The architecture remains prohibited from causal or Null benchmark exposure.

A retry is not currently permitted. The accepted provider-adapter decision explicitly froze zero automatic retries and required return to the referee after provider/transport failure. Any new call would therefore require a new explicit referee ruling.

## 5. Possible recovery paths for referee adjudication

These are options for adjudication, not proposed changes already adopted.

### A. Permit a narrowly revised provider record contract and replacement qualification

The adapter could be revised so that a completed response without an interaction ID is still captured as a protocol record with `interaction_id = null`, while preserving request hash, response-text hash, returned model, status, and provider usage when available. The trusted Critic schema and scientific scoring rules would remain unchanged.

Because the original CQ-1 request already consumed provider inference, repeating CQ-1 would be an additional exposure and must be explicitly authorized as a replacement qualification call. It must not be hidden as an ordinary retry.

### B. Preserve the strict interaction-ID requirement and terminate V1 provider qualification

If the referee considers a missing interaction ID incompatible with the frozen provider contract, the current abort can remain terminal for this V1 provider configuration.

### C. Authorize additional non-scientific transport characterization before deciding

A new synthetic provider call independent of all three Critic fixtures and all benchmark generators could test the exact `store=false` response envelope. This would still be a new provider call and therefore requires explicit referee authorization before execution.

## 6. Requested ruling

Please choose one of the following, or provide an equivalent explicit ruling:

1. **AUTHORIZE NARROW PROVIDER-RECORD REVISION AND REPLACEMENT CRITIC QUALIFICATION**;
2. **AUTHORIZE INDEPENDENT TRANSPORT CHARACTERIZATION ONLY**;
3. **TERMINATE V1 PROVIDER QUALIFICATION**;
4. **HOLD — OTHER INVESTIGATION REQUIRED**.

Until such a ruling is recorded, no further Gemini request and no benchmark exposure is authorized.
