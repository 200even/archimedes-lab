# Archimedes V1 — Gemini Provider Adapter Freeze Draft

**Status:** FROZEN DRAFT FOR REFEREE REVIEW — NO PROVIDER QUALIFICATION OR BENCHMARK EXPOSURE AUTHORIZED

This document preregisters the exact provider-transport semantics proposed for V1 before any live Gemini call is used for the Critic safeguard or any causal/Null benchmark exposure.

The implementation is `archimedes_v0/v1_gemini_backend.py`. All current tests use an injected fake HTTP transport; no live Gemini request has been made by this implementation.

## 1. Why direct REST

V1 uses a direct HTTPS adapter rather than the Google Python SDK. This removes SDK-managed retry/session behavior from the scientific execution path and makes the exact request body, headers, timeout, and one-attempt policy auditable in repository code.

Current official Gemini documentation identifies the Interactions REST endpoint as:

`POST https://generativelanguage.googleapis.com/v1beta/interactions`

and documents `gemini-3.7-flash`, `response_format`, `store`, `stream`, `background`, `generation_config.seed`, `thinking_level`, `thinking_summaries`, `tool_choice`, and provider usage token fields.

Reference:
- https://ai.google.dev/api/interactions-api-v1
- https://ai.google.dev/gemini-api/docs/latest-model
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/interactions-breaking-changes-may-2026

## 2. Exact frozen request surface

Every V1 model call is one non-streaming POST to:

`https://generativelanguage.googleapis.com/v1beta/interactions`

Headers:

- `Content-Type: application/json`
- `Accept: application/json`
- `x-goog-api-key: <runtime secret>`
- `Api-Revision: 2026-05-20`

The API revision explicitly requests the current `steps` / polymorphic `response_format` schema. The May 2026 migration documentation says the new schema became mandatory after the legacy sunset; the explicit revision header is retained as an auditable declaration of which response contract the adapter was written against.

Every request body contains exactly these scientific-control fields:

```json
{
  "model": "gemini-3.7-flash",
  "input": "<canonical JSON payload string>",
  "system_instruction": "<exact frozen role prompt>",
  "response_format": {
    "type": "text",
    "mime_type": "application/json",
    "schema": "<exact frozen role schema>"
  },
  "stream": false,
  "store": false,
  "background": false,
  "generation_config": {
    "max_output_tokens": "<4096 or 2048 according to frozen slot>",
    "seed": 20260902,
    "thinking_level": "high",
    "thinking_summaries": "none",
    "tool_choice": "none"
  }
}
```

No `tools` field is sent. No `previous_interaction_id` is sent. No persistent interaction state is used. No temperature, top-p, top-k, candidate-count, or thinking-budget parameter is sent.

The machine-readable Archimedes payload is serialized with sorted JSON keys and compact separators before being placed in `input`, so Python mapping insertion order cannot change provider input bytes.

## 3. Fixed decoding seed

Proposed frozen decoding seed:

`20260902`

The same seed is sent on every Full and Flat call. It is not derived from the world, arm, condition, role, or outcome.

Rationale: provider documentation describes `seed` as a decoding seed for reproducibility. A single arm-independent constant closes a researcher degree of freedom without injecting benchmark information or creating an arm-specific randomization schedule.

The seed does **not** create a claim of bit-exact provider determinism across hidden model revisions or infrastructure. Provider response metadata and realized output remain part of the immutable run record.

## 4. Thinking configuration

Every call uses:

- `thinking_level = high`
- `thinking_summaries = none`

Thought summaries are deliberately suppressed. The adapter ignores `thought` steps except their existence; it never stores thought text and never passes thought material across roles.

Provider usage accounting retains numeric `total_thought_tokens` when reported.

## 5. Structured output

The provider receives the exact authorized static JSON schema loaded from `V1_SCHEMA_FREEZE.json`.

The only transformation is moving internal references from `#/agent_facing/<Name>` to standard JSON-Schema `$defs` references so that the same frozen constraints form a self-contained provider schema. No cardinality, entity-key, batch-size, or other scientific constraint changes.

The adapter requires a completed response whose model-output text parses as one JSON object. Pydantic/Broker validation then applies the trusted semantic contract.

Unexpected function/tool/action steps are fatal provider-protocol errors because V1 declares no tools and freezes `tool_choice=none`.

## 6. Timeout and no-retry policy

Frozen wall-clock timeout per HTTP attempt:

`300.0 seconds`

**Automatic retries: exactly zero.**

The adapter contains no retry loop. A network error, timeout, non-2xx HTTP result, malformed provider response, non-`completed` interaction, unexpected step type, or wrong returned model identifier raises `V1ProviderError`.

That error is intentionally not converted to a scientific score by the orchestrator. Scientific execution must halt before any further benchmark exposure and return to the referee/operator. There is no same-world retry, top-up call, or replacement call.

Rationale: an automatic retry can duplicate hidden provider compute after an ambiguous network failure and can produce arm-dependent inference expenditure. Aborting the scientific run is operationally harsher but preserves the compute and exposure accounting boundary.

The 300-second timeout is not an inference-compute budget. It is only the maximum time the client waits for the one permitted HTTP attempt.

## 7. Response/version firewall

A valid response must report:

- `status == "completed"`
- `model == "gemini-3.7-flash"`
- a nonempty interaction ID
- a `steps` array containing model text and no forbidden tool/action step.

Any different returned model identifier aborts.

### Important provider limitation

The current Interactions API response schema documents the returned `model` identifier, but does not expose a separately documented immutable serving-build/version identifier for `gemini-3.7-flash` in the Interaction resource. Therefore V1 can mechanically freeze and verify:

1. the requested stable model ID;
2. the returned model ID;
3. the explicit API revision;
4. the exact request configuration;
5. request/response hashes and usage metadata.

It cannot, from the documented Interaction response alone, prove that Google has not changed the server-side weights behind the same stable GA model ID.

This limitation must be acknowledged by the referee before benchmark exposure. We must not claim stronger provider-version reproducibility than the API exposes.

## 8. Trusted usage record

For every successful call the adapter records, outside all model contexts:

- interaction ID;
- returned model ID;
- status;
- role;
- task;
- round index;
- slot max-output tokens;
- SHA-256 of canonical request body;
- SHA-256 of returned structured-output text;
- `total_input_tokens` when reported;
- `total_output_tokens` when reported;
- `total_thought_tokens` when reported;
- `total_tokens` when reported;
- `total_tool_use_tokens` when reported.

No thought text is retained.

These records provide the realized-compute audit used for `R_compute`.

## 9. Live-call order

No causal or Null benchmark call is authorized by this document.

If the referee accepts this adapter contract, the only live Gemini operation authorized next should be the already-preregistered **three-cycle independent Critic safeguard** in `V1_CRITIC_QUALIFICATION_FIXTURES.json`.

The fixture file and qualification harness were committed before any live provider qualification. The model-visible payload excludes every `trusted_*` expected-answer field.

If all three eligible cycles miss the preregistered contradiction-revealing intervention, the Critic safeguard fails and benchmark execution remains prohibited.

A Critic qualification pass still does **not** itself authorize causal/Null exposure. The result and provider metadata must be committed and returned to the referee in the final pre-exposure checkpoint.

## 10. Requested referee rulings

Before any live provider call, please rule on:

**A. Fixed seed:** Accept one arm-independent decoding seed `20260902` for all V1 calls.

**B. Infrastructure policy:** Accept zero automatic retries and abort-before-further-exposure on any provider/transport failure.

**C. Timeout:** Accept a single-attempt 300-second client timeout as an operational bound rather than a scientific compute allocation.

**D. Model-version limitation:** Accept that the Interactions API exposes the returned stable model identifier but no separately documented immutable serving-build identifier in the Interaction response; therefore reproducibility claims will be limited accordingly.

**E. Next live operation:** If A-D are accepted, authorize only the three preregistered Critic safeguard calls. Do not authorize causal/Null benchmark exposure yet.
