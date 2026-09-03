# Archimedes V1 — Final Pre-Exposure Checkpoint

**Critic safeguard:** `ABORTED_PROVIDER_INFRASTRUCTURE`

**Execution commit:** `4c2e8d8bc10080c8d38952b4b6aa12bbabd5c290`

## Three preregistered cycles

- Cycle 0 `CQ-1`: target `(entity_01, 3)` — **NOT RUN**
- Cycle 1 `CQ-2`: target `(entity_05, 6)` — **NOT RUN**
- Cycle 2 `CQ-3`: target `(entity_10, 1)` — **NOT RUN**

Consecutive misses at termination: `None`.  Safeguard pass: `None`.

## Provider and compute record

- Requested/returned model contract: `gemini-3.7-flash`
- API revision: `2026-05-20`
- Seed: `20260902`
- Thinking level: `high`
- Thought summaries: `none`
- Timeout: `300.0` seconds
- Automatic retries: `0`
- Successful provider interactions recorded: `0`
- Total input tokens: `None`
- Total output tokens: `None`
- Total thought tokens: `None`
- Total tokens: `None`

## Integrity evidence

- Pre-call V1 Determinism run: `33754645287` — `success`
- Frozen B-schedule combined digest: `295888922dc662549a235f55795b5d810fdab31b2b86a6b196f9a2232af3d459`
- `V1_CRITIC_QUALIFICATION_RESULT.json` SHA-256: `7511fcce3430f47d733007d8c2764fb7796d648721cdc50bceb664d2e7b88555`
- `V1_CRITIC_QUALIFICATION_USAGE.json` SHA-256: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`

No causal or Null benchmark world was exposed during this qualification. A Critic safeguard pass does **not** itself authorize benchmark exposure. The execution guard remains locked.

## Requested referee ruling

**`HOLD — REVISE/INVESTIGATE`**
