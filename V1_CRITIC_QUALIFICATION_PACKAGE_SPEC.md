# Archimedes V1 — Critic Qualification Evidence Package

**Status:** FROZEN BEFORE LIVE CRITIC QUALIFICATION

This document defines the complete evidence package that must be produced from the three authorized Critic safeguard calls before any request for causal/Null benchmark exposure. It is packaging/audit logic only; it does not alter the fixture, prompt, hypothesis class, intervention-selection criterion, or provider call semantics.

## 1. Package contents

The final referee handoff must contain exactly these primary artifacts:

1. `V1_CRITIC_QUALIFICATION_RESULT.json` — machine-readable canonical result and per-cycle evidence.
2. `V1_CRITIC_QUALIFICATION_USAGE.json` — canonical trusted provider usage records, one record per successful live call.
3. `V1_FINAL_PREEXPOSURE_MANIFEST.json` — exact source/configuration hashes and Git/CI provenance.
4. `REFEREE_CHECKPOINT_V1_FINAL_PREEXPOSURE.md` — human-readable checkpoint derived from the machine-readable artifacts, with no additional scientific scoring decisions.

No provider thought text, thought signature, chain-of-thought, API key, authorization header, or secret may appear in any artifact.

## 2. Result JSON

`V1_CRITIC_QUALIFICATION_RESULT.json` records:

- schema/package version;
- execution status;
- fixture-set identifier and SHA-256 of the exact fixture file;
- execution Git commit SHA;
- exact three-cycle order;
- for each cycle:
  - `cycle_id`;
  - preregistered target `(entity_id, action_value)`;
  - the complete ten-intervention structured batch returned by the Critic, canonicalized without modification;
  - boolean `selected_revealing_intervention`;
  - interaction ID;
  - returned model ID;
  - request-body SHA-256;
  - structured-response-text SHA-256;
  - provider usage counts when reported;
- final `consecutive_misses` exactly as defined by the frozen harness;
- final `passes_safeguard`.

The result may have only three terminal execution classes:

- `COMPLETED_PASS` — all three authorized provider calls completed and `passes_safeguard=true`;
- `COMPLETED_FAIL` — all three authorized provider calls completed and the frozen safeguard criterion failed;
- `ABORTED_PROVIDER_INFRASTRUCTURE` — a provider/transport/protocol failure occurred. No automatic retry is permitted and no later authorized Critic cycle may be run in that execution attempt. This state is not converted into a scientific pass or fail and requires referee adjudication.

A normative-schema-invalid completed model response is a semantic model failure, not an infrastructure retry opportunity. The execution record must retain the provider usage/hash metadata that exists up to that point and report the exact trusted validator failure. No replacement call is permitted without a referee ruling.

## 3. Usage JSON

`V1_CRITIC_QUALIFICATION_USAGE.json` is the canonical serialization of the backend's trusted `GeminiUsageRecord` objects in call order. It contains no response prose and no thought content.

Each successful provider call records:

- interaction ID;
- returned model ID;
- provider status;
- role;
- task;
- round index;
- max-output-token slot;
- canonical request-body SHA-256;
- structured-output-text SHA-256;
- total input/output/thought/tool-use/overall token counts when the provider reports them.

The result artifact and usage artifact must cross-check interaction IDs, request hashes, response hashes, model IDs, and call order exactly.

## 4. Final pre-exposure manifest

`V1_FINAL_PREEXPOSURE_MANIFEST.json` freezes the precise implementation that produced the safeguard result. It records SHA-256 and Git blob SHA for at least:

- `archimedes_v0/v1_protocol.py`;
- `archimedes_v0/v1_broker.py`;
- `archimedes_v0/v1_orchestrator.py`;
- `archimedes_v0/v1_agent_interfaces.py`;
- `archimedes_v0/v1_gemini_backend.py`;
- `archimedes_v0/v1_critic_qualification.py`;
- `V1_CRITIC_QUALIFICATION_FIXTURES.json`;
- `V1_SCHEMA_FREEZE.json`;
- `V1_PROMPT_MANIFEST.json` and all three prompt files;
- `V1_PROVIDER_ADAPTER_FREEZE_DRAFT.md`;
- `V1_SCHEDULE_DIGEST_MANIFEST.json`;
- the V1 determinism workflow and the complete V1 test suite relevant to the freeze.

It also records:

- execution commit SHA;
- Python version;
- pinned dependency versions;
- endpoint;
- API revision;
- requested/returned model ID;
- seed `20260902`;
- thinking level `high`;
- thought summaries `none`;
- timeout `300.0` seconds;
- automatic retry count `0`;
- `store=false`, `stream=false`, `background=false`, tools disabled;
- exact GitHub Actions run IDs and conclusions establishing pre-call synthetic CI integrity;
- frozen cross-hash-seed B-schedule digest;
- SHA-256 of the result and usage artifacts.

## 5. Referee checkpoint

`REFEREE_CHECKPOINT_V1_FINAL_PREEXPOSURE.md` must be a concise rendering of the immutable evidence rather than a new analysis stage. It reports:

- whether the Critic safeguard passed, failed, or aborted;
- the three cycle outcomes and selected target hits;
- provider/model/API metadata;
- usage totals for the three calls;
- exact execution commit and source/config hashes;
- latest required CI run IDs and conclusions;
- explicit statement that no causal or Null benchmark model exposure occurred;
- explicit statement that a Critic pass does **not** itself authorize benchmark exposure;
- a single requested ruling: `AUTHORIZE V1 BENCHMARK EXPOSURE`, `HOLD — REVISE/INVESTIGATE`, or `TERMINATE V1` as applicable.

## 6. Auditability requirements

The referee must be able to recompute each cycle's hit from only the committed fixture and committed returned ten-intervention batch. No subjective interpretation is used.

The request SHA can be independently reconstructed from the execution commit, fixture, deterministic payload builder, exact prompt, projected response schema, and frozen provider configuration. The API key is a header secret and is not part of the canonical request body hash.

All JSON artifacts use UTF-8, sorted keys, compact separators, and newline termination. Their SHA-256 values are computed from the exact committed bytes.

## 7. Exposure firewall

Creation of these artifacts, successful Critic qualification, and green CI do not unlock causal or Null execution. The execution guard remains locked until a subsequent explicit referee decision authorizes benchmark exposure.
