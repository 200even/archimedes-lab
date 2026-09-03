from __future__ import annotations

from pathlib import Path

from archimedes_v0.v1_agent_interfaces import V1Critic
from archimedes_v0.v1_gemini_backend import GeminiUsageRecord, InMemoryUsageSink
from archimedes_v0.v1_live_qualification import execute_authorized_critic_safeguard


TARGETS = {
    0: ("entity_01", 3),
    1: ("entity_05", 6),
    2: ("entity_10", 1),
}


class AuditedFakeBackend:
    def __init__(self, sink: InMemoryUsageSink, *, hit_cycles=(), invalid_cycles=()):
        self.sink = sink
        self.hit_cycles = set(hit_cycles)
        self.invalid_cycles = set(invalid_cycles)
        self.calls = 0

    def invoke(self, *, role, system_prompt, payload, response_schema, max_output_tokens):
        cycle = payload["round_index"]
        self.calls += 1
        self.sink.append(
            GeminiUsageRecord(
                interaction_id=f"int-fake-{cycle}",
                returned_model="gemini-3.7-flash",
                status="completed",
                role=role,
                task=payload["task"],
                round_index=cycle,
                max_output_tokens=max_output_tokens,
                request_sha256=f"{cycle + 1:064x}",
                response_text_sha256=f"{cycle + 11:064x}",
                total_input_tokens=100 + cycle,
                total_output_tokens=20,
                total_thought_tokens=30,
                total_tokens=150 + cycle,
                total_tool_use_tokens=0,
            )
        )
        rows = []
        used = set()
        if cycle in self.hit_cycles:
            entity, action = TARGETS[cycle]
            rows.append(
                {
                    "experiment_id": f"E-hit-{cycle}",
                    "objective": "discriminate",
                    "paradigm": "A",
                    "entity_id": entity,
                    "action_value": action,
                    "target_hypothesis_ids": [f"H-CQ{cycle + 1}"],
                }
            )
            used.add((entity, action))
        cursor = 0
        required = 9 if cycle in self.invalid_cycles else 10
        while len(rows) < required:
            pair = (f"entity_{12 + ((cursor // 8) % 4):02d}", cursor % 8)
            cursor += 1
            if pair in used or pair == TARGETS[cycle]:
                continue
            used.add(pair)
            rows.append(
                {
                    "experiment_id": f"E-fill-{cycle}-{len(rows)}",
                    "objective": "discriminate",
                    "paradigm": "A",
                    "entity_id": pair[0],
                    "action_value": pair[1],
                    "target_hypothesis_ids": [f"H-CQ{cycle + 1}"],
                }
            )
        return {"experiments": rows}


def test_live_execution_uses_exactly_three_calls_and_frozen_hit_rule():
    sink = InMemoryUsageSink()
    backend = AuditedFakeBackend(sink, hit_cycles={1})
    result = execute_authorized_critic_safeguard(V1Critic(backend, "critic"), sink)
    assert backend.calls == 3
    assert len(sink.records) == 3
    assert result.terminal_execution_class == "COMPLETED_PASS"
    assert result.passes_safeguard is True
    assert [c.selected_revealing_intervention for c in result.cycles] == [False, True, False]
    assert result.consecutive_misses == 1


def test_completed_normative_schema_failure_is_one_miss_not_a_retry():
    sink = InMemoryUsageSink()
    backend = AuditedFakeBackend(sink, hit_cycles={2}, invalid_cycles={0})
    result = execute_authorized_critic_safeguard(V1Critic(backend, "critic"), sink)
    assert backend.calls == 3
    assert len(sink.records) == 3
    assert result.cycles[0].selected_batch is None
    assert result.cycles[0].selected_revealing_intervention is False
    assert result.cycles[0].semantic_validation_error
    assert result.cycles[2].selected_revealing_intervention is True
    assert result.terminal_execution_class == "COMPLETED_PASS"


def test_live_workflow_is_one_shot_trigger_only_and_rerun_guarded():
    text = Path(".github/workflows/v1_critic_qualification_live.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" not in text
    assert "V1_CRITIC_QUALIFICATION_TRIGGER.txt" in text
    assert "github.run_attempt == 1" in text
    assert "git log --format=%H -- V1_CRITIC_QUALIFICATION_TRIGGER.txt" in text
    assert "GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}" in text
    assert "actions/upload-artifact@v4" in text
    assert "fetch-depth: 0" in text


def test_live_runner_has_no_benchmark_generator_import_path():
    text = Path("scripts/run_v1_critic_qualification_live.py").read_text(encoding="utf-8")
    forbidden_imports = ("archimedes_v0.generator", "archimedes_v0.world", "from archimedes_v0 import generator")
    assert all(token not in text for token in forbidden_imports)
