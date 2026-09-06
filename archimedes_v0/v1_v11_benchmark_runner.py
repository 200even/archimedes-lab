from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .analysis_plan import evaluate_registered_primary
from .generator import generate_world
from .v1_agent_interfaces import V1Conjecturer
from .v1_broker import V1Broker
from .v1_gemini_backend import GeminiInteractionsBackend, InMemoryUsageSink, V1ProviderError
from .v1_orchestrator import V1FlatOrchestrator, V1FullOrchestrator
from .v1_v11_benchmark_agents import V11BenchmarkSelector, V11FlatAgent
from .world import HiddenWorldRuntime

ROOT = Path(__file__).resolve().parents[1]
FREEZE_PATH = ROOT / "V11_BENCHMARK_EXECUTION_FREEZE.json"
PROMPT_MANIFEST_PATH = ROOT / "V1_PROMPT_MANIFEST.json"
NULL_PASS_PATH = ROOT / "V11_NULL_VANGUARD_PASS.json"


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def derive_world_seed(phase: str, index: int) -> int:
    if phase not in {"vanguard", "paired"}:
        raise ValueError("unknown frozen benchmark phase")
    if type(index) is not int or not 0 <= index < 100:
        raise ValueError("benchmark world index must be 0..99")
    token = f"Archimedes-V1.1-Benchmark|{phase}|{index:03d}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(token).digest()[:8], "big") & ((1 << 63) - 1)


def opaque_world_id(phase: str, index: int) -> str:
    if phase not in {"vanguard", "paired"}:
        raise ValueError("unknown frozen benchmark phase")
    if type(index) is not int or not 0 <= index < 100:
        raise ValueError("benchmark world index must be 0..99")
    token = f"Archimedes-V1.1-WorldID|{phase}|{index:03d}".encode("utf-8")
    return "v11-w-" + hashlib.sha256(token).hexdigest()[:20]


def _load_freeze() -> dict[str, Any]:
    raw = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if raw.get("status") != "FROZEN_BEFORE_FIRST_BENCHMARK_MODEL_EXPOSURE":
        raise RuntimeError("V1.1 benchmark execution freeze is not active")
    if raw.get("benchmark_exposure_authorized") is not True:
        raise RuntimeError("V1.1 benchmark exposure is not authorized")
    if raw.get("sequence", [None])[0] != "null_vanguard":
        raise RuntimeError("frozen benchmark sequence does not begin with Null vanguard")
    return raw


def _load_prompt(name: str) -> str:
    manifest = json.loads(PROMPT_MANIFEST_PATH.read_text(encoding="utf-8"))
    row = manifest["prompts"][name]
    path = ROOT / row["path"]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise RuntimeError(f"{name} prompt hash mismatch")
    return raw.decode("utf-8")


def _usage_totals(records) -> dict[str, int | None]:
    fields = (
        "total_input_tokens",
        "total_output_tokens",
        "total_thought_tokens",
        "total_tool_use_tokens",
        "total_tokens",
    )
    out: dict[str, int | None] = {}
    for field in fields:
        values = [getattr(record, field) for record in records]
        out[field] = sum(v for v in values if v is not None) if values and all(v is not None for v in values) else None
    return out


def _write(path: Path, value: Any) -> str:
    data = canonical_json_bytes(value)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _hidden_dict(hidden) -> dict[str, Any]:
    return asdict(hidden)


def _new_full(runtime: HiddenWorldRuntime, backend: GeminiInteractionsBackend) -> V1FullOrchestrator:
    broker = V1Broker(runtime)
    conjecturer = V1Conjecturer(backend, _load_prompt("conjecturer"))
    critic = V11BenchmarkSelector(backend, _load_prompt("critic"), role="critic")
    return V1FullOrchestrator(broker, conjecturer, critic)  # structural select interface


def _new_flat(runtime: HiddenWorldRuntime, backend: GeminiInteractionsBackend) -> V1FlatOrchestrator:
    broker = V1Broker(runtime)
    flat = V11FlatAgent(backend, _load_prompt("flat"))
    return V1FlatOrchestrator(broker, flat)  # structural generate/select/commit interface


def run_null_vanguard(out_dir: Path) -> tuple[int, dict[str, Any]]:
    freeze = _load_freeze()
    usage_sink = InMemoryUsageSink()
    backend = GeminiInteractionsBackend(usage_sink=usage_sink)
    worlds: list[dict[str, Any]] = []
    positives = 0
    provider_failure: str | None = None

    for index in range(100):
        seed = derive_world_seed("vanguard", index)
        world_id = opaque_world_id("vanguard", index)
        _, hidden, report = generate_world(seed, null_world=True, max_attempts=1000, world_id=world_id)
        if report.get("accepted") is not True:
            raise RuntimeError("frozen Null generator rejected a Null world")
        hidden_dict = _hidden_dict(hidden)
        start_usage = len(usage_sink.records)
        try:
            orchestrator = _new_full(HiddenWorldRuntime(hidden_dict), backend)
            result = orchestrator.run(execution_authorized=True)
        except V1ProviderError as exc:
            provider_failure = f"world_index={index}:{type(exc).__name__}:{exc}"
            break
        end_usage = len(usage_sink.records)
        records = usage_sink.records[start_usage:end_usage]
        # Positive is exactly advancement through the empirical A gate into B.
        positive = result.b_calibration_schedule_digest is not None
        positives += int(positive)
        worlds.append(
            {
                "world_index": index,
                "opaque_world_id": world_id,
                "generator_seed": seed,
                "hidden_spec_sha256": sha256_json(hidden_dict),
                "result": asdict(result),
                "null_positive": positive,
                "provider_calls": len(records),
                "provider_usage": _usage_totals(records),
            }
        )
        if positives >= 5:
            # Five positives already make FPR >= .05 even if every unexecuted
            # world would be negative. Stop immediately under Hallucination Kill.
            break

    if provider_failure is not None:
        terminal = "ABORTED_PROVIDER_INFRASTRUCTURE"
    elif positives >= 5:
        terminal = "HALLUCINATION_KILL"
    elif len(worlds) == 100:
        terminal = "NULL_PASS"
    else:
        raise AssertionError("Null vanguard ended without a terminal condition")

    evidence = {
        "protocol_version": "V1.1",
        "phase": "null_vanguard",
        "terminal_execution_class": terminal,
        "planned_worlds": 100,
        "executed_worlds": len(worlds),
        "positive_count": positives,
        "fpr_lower_bound_over_registered_100": positives / 100.0,
        "hallucination_kill": positives >= 5,
        "provider_failure": provider_failure,
        "worlds": worlds,
        "aggregate_provider_calls": len(usage_sink.records),
        "aggregate_provider_usage": _usage_totals(usage_sink.records),
        "seed_freeze_sha256": hashlib.sha256(FREEZE_PATH.read_bytes()).hexdigest(),
        "causal_world_exposure_occurred": False,
    }
    _write(out_dir / "V11_NULL_VANGUARD_RESULT.json", evidence)
    _write(out_dir / "V11_NULL_VANGUARD_USAGE.json", [asdict(r) for r in usage_sink.records])
    return (2 if terminal == "ABORTED_PROVIDER_INFRASTRUCTURE" else 0), evidence


def _require_null_pass() -> dict[str, Any]:
    if not NULL_PASS_PATH.is_file():
        raise RuntimeError("causal phase locked: V11_NULL_VANGUARD_PASS.json is absent")
    raw = json.loads(NULL_PASS_PATH.read_text(encoding="utf-8"))
    if raw.get("status") != "NULL_VANGUARD_PASSED" or raw.get("positive_count", 999) >= 5:
        raise RuntimeError("causal phase locked: Null vanguard did not pass")
    return raw


def run_causal_paired(out_dir: Path) -> tuple[int, dict[str, Any]]:
    _load_freeze()
    null_pass = _require_null_pass()
    full_usage = InMemoryUsageSink()
    flat_usage = InMemoryUsageSink()
    full_backend = GeminiInteractionsBackend(usage_sink=full_usage)
    flat_backend = GeminiInteractionsBackend(usage_sink=flat_usage)
    pairs: list[dict[str, Any]] = []
    provider_failure: str | None = None

    for index in range(100):
        seed = derive_world_seed("paired", index)
        world_id = opaque_world_id("paired", index)
        _, hidden, report = generate_world(seed, null_world=False, max_attempts=1000, world_id=world_id)
        if report.get("accepted") is not True:
            raise RuntimeError("frozen causal generator failed admission")
        hidden_dict = _hidden_dict(hidden)
        full_start = len(full_usage.records)
        flat_start = len(flat_usage.records)
        arm_order = ("full", "flat") if index % 2 == 0 else ("flat", "full")
        arm_results: dict[str, Any] = {}
        try:
            for arm in arm_order:
                runtime = HiddenWorldRuntime(hidden_dict)
                if arm == "full":
                    result = _new_full(runtime, full_backend).run(execution_authorized=True)
                else:
                    result = _new_flat(runtime, flat_backend).run(execution_authorized=True)
                arm_results[arm] = result
        except V1ProviderError as exc:
            provider_failure = f"world_index={index}:arm={arm}:{type(exc).__name__}:{exc}"
            break

        full_records = full_usage.records[full_start:]
        flat_records = flat_usage.records[flat_start:]
        pairs.append(
            {
                "world_index": index,
                "opaque_world_id": world_id,
                "generator_seed": seed,
                "hidden_spec_sha256": sha256_json(hidden_dict),
                "generator_validation_sha256": sha256_json(report),
                "arm_order": list(arm_order),
                "full_result": asdict(arm_results["full"]),
                "flat_result": asdict(arm_results["flat"]),
                "full_provider_calls": len(full_records),
                "flat_provider_calls": len(flat_records),
                "full_provider_usage": _usage_totals(full_records),
                "flat_provider_usage": _usage_totals(flat_records),
            }
        )

    if provider_failure is not None:
        terminal = "ABORTED_PROVIDER_INFRASTRUCTURE"
        evidence = {
            "protocol_version": "V1.1",
            "phase": "causal_paired",
            "terminal_execution_class": terminal,
            "completed_pairs": len(pairs),
            "provider_failure": provider_failure,
            "pairs": pairs,
            "null_pass_record_sha256": sha256_json(null_pass),
        }
        _write(out_dir / "V11_CAUSAL_RESULT.json", evidence)
        _write(out_dir / "V11_CAUSAL_FULL_USAGE.json", [asdict(r) for r in full_usage.records])
        _write(out_dir / "V11_CAUSAL_FLAT_USAGE.json", [asdict(r) for r in flat_usage.records])
        return 2, evidence

    if len(pairs) != 100:
        raise AssertionError("registered causal phase requires exactly 100 completed pairs")

    # Binding order: compute audit before extracting/evaluating D4 world scores.
    full_total_tokens = _usage_totals(full_usage.records)["total_tokens"]
    flat_total_tokens = _usage_totals(flat_usage.records)["total_tokens"]
    if full_total_tokens is None or flat_total_tokens is None or flat_total_tokens <= 0:
        compute_ratio = None
        compute_valid_for_full_win = False
        compute_status = "COMPUTE_AUDIT_INVALID"
    else:
        compute_ratio = full_total_tokens / flat_total_tokens
        compute_valid_for_full_win = compute_ratio <= 1.05
        compute_status = "VALID" if compute_valid_for_full_win else "FULL_WIN_INVALID_IF_NOMINAL"

    # Only after the aggregate compute audit above do we evaluate D4 scores.
    full_scores = [float(row["full_result"]["world_score"]) for row in pairs]
    flat_scores = [float(row["flat_result"]["world_score"]) for row in pairs]
    comparison = evaluate_registered_primary(full_scores, flat_scores)
    scientific_success = bool(comparison.primary_success and compute_valid_for_full_win)

    evidence = {
        "protocol_version": "V1.1",
        "phase": "causal_paired",
        "terminal_execution_class": "COMPLETED",
        "completed_pairs": 100,
        "provider_failure": None,
        "compute_audit": {
            "status": compute_status,
            "full_total_provider_tokens": full_total_tokens,
            "flat_total_provider_tokens": flat_total_tokens,
            "R_compute": compute_ratio,
            "full_win_valid_if_nominal": compute_valid_for_full_win,
            "upper_bound": 1.05,
        },
        "primary_comparison": asdict(comparison),
        "scientific_success": scientific_success,
        "pairs": pairs,
        "null_pass_record_sha256": sha256_json(null_pass),
    }
    _write(out_dir / "V11_CAUSAL_RESULT.json", evidence)
    _write(out_dir / "V11_CAUSAL_FULL_USAGE.json", [asdict(r) for r in full_usage.records])
    _write(out_dir / "V11_CAUSAL_FLAT_USAGE.json", [asdict(r) for r in flat_usage.records])
    return 0, evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("null", "causal"))
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY missing; zero benchmark requests sent")

    if args.phase == "null":
        code, _ = run_null_vanguard(out_dir)
    else:
        code, _ = run_causal_paired(out_dir)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
