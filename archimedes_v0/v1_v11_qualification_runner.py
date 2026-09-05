from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .v1_critic_qualification import FIXTURE_PATH
from .v1_gemini_backend import (
    GEMINI_API_REVISION,
    GEMINI_INTERACTIONS_ENDPOINT,
    GEMINI_MODEL_ID,
    GEMINI_SEED,
    GEMINI_THINKING_LEVEL,
    GEMINI_THINKING_SUMMARIES,
    GEMINI_TIMEOUT_SECONDS,
    GeminiInteractionsBackend,
    InMemoryUsageSink,
)
from .v1_live_qualification import LiveCriticExecution, _pending_cycle, execute_authorized_critic_safeguard, usage_for_cycle
from .v1_v11_critic import V11Critic

ROOT = Path(__file__).resolve().parents[1]
FREEZE_PATH = ROOT / "V11_CRITIC_LIVE_EXECUTION_FREEZE.json"
PROMPT_MANIFEST_PATH = ROOT / "V1_PROMPT_MANIFEST.json"
SCHEDULE_MANIFEST_PATH = ROOT / "V1_SCHEDULE_DIGEST_MANIFEST.json"

HASH_PATHS = (
    "archimedes_v0/v1_protocol.py",
    "archimedes_v0/v1_agent_interfaces.py",
    "archimedes_v0/v1_gemini_backend.py",
    "archimedes_v0/v1_critic_qualification.py",
    "archimedes_v0/v1_live_qualification.py",
    "archimedes_v0/v1_v11_critic.py",
    "archimedes_v0/v1_v11_qualification_runner.py",
    ".github/workflows/v1_v11_critic_qualification.yml",
    "V1_CRITIC_QUALIFICATION_FIXTURES.json",
    "V11_CRITIC_LIVE_EXECUTION_FREEZE.json",
    "REFEREE_DECISION_V11_IMPLEMENTATION_AUTHORIZED.md",
    "REFEREE_CHECKPOINT_V11_BROKER_ASSIGNED_IDS.md",
    "V1_PROMPT_MANIFEST.json",
    "V1_SCHEMA_FREEZE.json",
    "v1_design/prompts/critic_system.txt",
    "tests/test_v1_v11_broker_ids.py",
)


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _write_json(path: Path, value: Any) -> str:
    data = _canonical_bytes(value)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _blob_sha(relative: str) -> str:
    return _git("hash-object", relative)


def _file_manifest() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for relative in HASH_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"required V1.1 freeze path missing: {relative}")
        rows[relative] = {
            "sha256": _sha256_file(path),
            "git_blob_sha": _blob_sha(relative),
            "bytes": path.stat().st_size,
        }
    return rows


def _load_freeze() -> dict[str, Any]:
    raw = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if raw.get("status") != "FROZEN_FOR_AUTHORIZED_V11_THREE_CALL_CRITIC_SAFEGUARD":
        raise RuntimeError("V1.1 live execution freeze is absent or not frozen")
    if raw.get("authorized_live_critic_calls") != 3:
        raise RuntimeError("V1.1 freeze must authorize exactly three calls")
    if raw.get("benchmark_exposure_authorized") is not False:
        raise RuntimeError("V1.1 freeze must explicitly prohibit benchmark exposure")
    ci = raw.get("pre_call_v11_determinism")
    if not isinstance(ci, dict) or ci.get("conclusion") != "success" or not isinstance(ci.get("run_id"), int):
        raise RuntimeError("V1.1 freeze must identify successful pre-call determinism CI")
    return raw


def _critic_prompt() -> str:
    manifest = json.loads(PROMPT_MANIFEST_PATH.read_text(encoding="utf-8"))
    row = manifest["prompts"]["critic"]
    path = ROOT / row["path"]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise RuntimeError("Critic prompt hash does not match frozen prompt manifest")
    return raw.decode("utf-8")


def _result_document(execution, records, execution_commit: str) -> dict[str, Any]:
    rows = []
    for cycle in execution.cycles:
        record = usage_for_cycle(cycle, records)
        rows.append(
            {
                "cycle_index": cycle.cycle_index,
                "cycle_id": cycle.cycle_id,
                "target_entity_id": cycle.target_entity_id,
                "target_action_value": cycle.target_action_value,
                "selected_batch": cycle.selected_batch,
                "selected_revealing_intervention": cycle.selected_revealing_intervention,
                "interaction_id": record.interaction_id if record else None,
                "returned_model": record.returned_model if record else None,
                "provider_status": record.status if record else None,
                "request_sha256": record.request_sha256 if record else None,
                "response_text_sha256": record.response_text_sha256 if record else None,
                "usage": {
                    "total_input_tokens": record.total_input_tokens if record else None,
                    "total_output_tokens": record.total_output_tokens if record else None,
                    "total_thought_tokens": record.total_thought_tokens if record else None,
                    "total_tool_use_tokens": record.total_tool_use_tokens if record else None,
                    "total_tokens": record.total_tokens if record else None,
                },
                "semantic_validation_error": cycle.semantic_validation_error,
            }
        )
    return {
        "package_version": "v11-critic-qualification-1",
        "protocol_version": "V1.1",
        "status": "LIVE_V11_RESULT",
        "terminal_execution_class": execution.terminal_execution_class,
        "execution_commit_sha": execution_commit,
        "fixture_set": execution.fixture_set,
        "fixture_file_sha256": _sha256_file(FIXTURE_PATH),
        "cycles": rows,
        "consecutive_misses": execution.consecutive_misses,
        "passes_safeguard": execution.passes_safeguard,
        "provider_failure": execution.provider_failure,
        "historical_v1_completed_fail_preserved": True,
        "historical_v1_replacement_run_id": 33873946136,
        "historical_provider_abort_run_id": 33781365337,
        "benchmark_exposure_occurred": False,
        "notes": "Fresh V1.1 qualification under broker-assigned bookkeeping IDs. Historical V1 results were not rescored or modified.",
    }


def _usage_totals(records) -> dict[str, int | None]:
    keys = ("total_input_tokens", "total_output_tokens", "total_thought_tokens", "total_tool_use_tokens", "total_tokens")
    out: dict[str, int | None] = {}
    for key in keys:
        values = [getattr(record, key) for record in records]
        out[key] = sum(value for value in values if value is not None) if any(value is not None for value in values) else None
    return out


def _checkpoint(execution, records, execution_commit: str, result_sha: str, usage_sha: str, freeze: dict[str, Any]) -> str:
    cycle_lines = []
    for cycle in execution.cycles:
        outcome = "HIT" if cycle.selected_revealing_intervention is True else "MISS" if cycle.selected_revealing_intervention is False else "NOT RUN"
        cycle_lines.append(
            f"- Cycle {cycle.cycle_index} `{cycle.cycle_id}`: target `({cycle.target_entity_id}, {cycle.target_action_value})` — **{outcome}**"
        )
    request = (
        "AUTHORIZE V1.1 BENCHMARK EXPOSURE"
        if execution.terminal_execution_class == "COMPLETED_PASS"
        else "HOLD — INVESTIGATE PROVIDER INFRASTRUCTURE"
        if execution.terminal_execution_class == "ABORTED_PROVIDER_INFRASTRUCTURE"
        else "TERMINATE V1.1"
    )
    totals = _usage_totals(records)
    ci = freeze["pre_call_v11_determinism"]
    return f"""# Archimedes V1.1 — Final Pre-Exposure Checkpoint\n\n**Critic safeguard:** `{execution.terminal_execution_class}`\n\n**Execution commit:** `{execution_commit}`\n\n## Three frozen cycles\n\n{chr(10).join(cycle_lines)}\n\nConsecutive misses at termination: `{execution.consecutive_misses}`. Safeguard pass: `{execution.passes_safeguard}`.\n\n## V1.1 interface correction\n\n`experiment_id` was absent from the model-facing Critic schema. Trusted code assigned canonical IDs from cycle index and array position only, then applied the existing normative `AExperimentBatch` validator. No other field was repaired or normalized.\n\nHistorical V1 remains permanently recorded as `COMPLETED_FAIL`; this V1.1 execution is a new protocol qualification and not a rescore or retry of V1.\n\n## Provider and compute record\n\n- Model: `{GEMINI_MODEL_ID}`\n- API revision: `{GEMINI_API_REVISION}`\n- Seed: `{GEMINI_SEED}`\n- Thinking level: `{GEMINI_THINKING_LEVEL}`\n- Thought summaries: `{GEMINI_THINKING_SUMMARIES}`\n- Timeout: `{GEMINI_TIMEOUT_SECONDS}` seconds\n- Automatic retries: `0`\n- Completed provider interactions recorded: `{len(records)}`\n- Total input tokens: `{totals['total_input_tokens']}`\n- Total output tokens: `{totals['total_output_tokens']}`\n- Total thought tokens: `{totals['total_thought_tokens']}`\n- Total tokens: `{totals['total_tokens']}`\n\n## Integrity evidence\n\n- Pre-call V1.1 determinism run: `{ci['run_id']}` — `{ci['conclusion']}`\n- `V11_CRITIC_QUALIFICATION_RESULT.json` SHA-256: `{result_sha}`\n- `V11_CRITIC_QUALIFICATION_USAGE.json` SHA-256: `{usage_sha}`\n\nNo causal or Null benchmark world was exposed. A V1.1 Critic pass does **not** itself authorize benchmark execution; explicit referee authorization remains required.\n\n## Requested referee ruling\n\n**`{request}`**\n"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="evidence-v11")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    execution_commit = os.environ.get("GITHUB_SHA") or _git("rev-parse", "HEAD")
    freeze = _load_freeze()
    usage_sink = InMemoryUsageSink()

    if not os.environ.get("GEMINI_API_KEY"):
        from .v1_critic_qualification import load_fixtures

        fixtures = load_fixtures()
        execution = LiveCriticExecution(
            fixture_set=fixtures["fixture_set"],
            cycles=tuple(_pending_cycle(cycle, i) for i, cycle in enumerate(fixtures["cycles"])),
            consecutive_misses=None,
            passes_safeguard=None,
            terminal_execution_class="ABORTED_PROVIDER_INFRASTRUCTURE",
            provider_failure="GEMINI_API_KEY missing; zero provider requests sent",
        )
    else:
        backend = GeminiInteractionsBackend(usage_sink=usage_sink)
        critic = V11Critic(backend, _critic_prompt())
        execution = execute_authorized_critic_safeguard(critic, usage_sink)

    result = _result_document(execution, usage_sink.records, execution_commit)
    usage = [asdict(record) for record in usage_sink.records]
    result_sha = _write_json(out_dir / "V11_CRITIC_QUALIFICATION_RESULT.json", result)
    usage_sha = _write_json(out_dir / "V11_CRITIC_QUALIFICATION_USAGE.json", usage)

    manifest = {
        "manifest_version": "v11-final-preexposure-1",
        "protocol_version": "V1.1",
        "status": "GENERATED_AFTER_AUTHORIZED_V11_CRITIC_SAFEGUARD",
        "execution_commit_sha": execution_commit,
        "terminal_execution_class": execution.terminal_execution_class,
        "source_and_config_files": _file_manifest(),
        "runtime": {
            "python": platform.python_version(),
            "pydantic": importlib.metadata.version("pydantic"),
            "z3_solver": importlib.metadata.version("z3-solver"),
        },
        "provider": {
            "endpoint": GEMINI_INTERACTIONS_ENDPOINT,
            "api_revision": GEMINI_API_REVISION,
            "requested_model": GEMINI_MODEL_ID,
            "returned_models": sorted({record.returned_model for record in usage_sink.records}),
            "seed": GEMINI_SEED,
            "thinking_level": GEMINI_THINKING_LEVEL,
            "thinking_summaries": GEMINI_THINKING_SUMMARIES,
            "timeout_seconds": GEMINI_TIMEOUT_SECONDS,
            "automatic_retry_count": 0,
            "store": False,
            "tools_enabled": False,
        },
        "pre_call_v11_determinism": freeze["pre_call_v11_determinism"],
        "frozen_implementation_commit_sha": freeze["frozen_implementation_commit_sha"],
        "historical_v1_completed_fail_preserved": True,
        "historical_v1_replacement_run_id": 33873946136,
        "historical_provider_abort_run_id": 33781365337,
        "result_sha256": result_sha,
        "usage_sha256": usage_sha,
        "successful_provider_calls": len(usage_sink.records),
        "benchmark_exposure_occurred": False,
    }
    _write_json(out_dir / "V11_FINAL_PREEXPOSURE_MANIFEST.json", manifest)
    (out_dir / "REFEREE_CHECKPOINT_V11_FINAL_PREEXPOSURE.md").write_text(
        _checkpoint(execution, usage_sink.records, execution_commit, result_sha, usage_sha, freeze),
        encoding="utf-8",
        newline="\n",
    )

    return 2 if execution.terminal_execution_class == "ABORTED_PROVIDER_INFRASTRUCTURE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
