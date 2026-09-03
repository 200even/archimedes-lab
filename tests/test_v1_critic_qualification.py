from __future__ import annotations

import json

from archimedes_v0.v1_agent_interfaces import V1Critic
from archimedes_v0.v1_critic_qualification import _agent_payload, load_fixtures, run_critic_qualification


TARGETS = {
    0: ("entity_01", 3),
    1: ("entity_05", 6),
    2: ("entity_10", 1),
}


class QualificationBackend:
    def __init__(self, *, hit_cycle: int | None):
        self.hit_cycle = hit_cycle
        self.calls = []

    def invoke(self, *, role, system_prompt, payload, response_schema, max_output_tokens):
        self.calls.append(payload)
        cycle = payload["round_index"]
        experiments = []
        used_pairs = set()
        if self.hit_cycle == cycle:
            pair = TARGETS[cycle]
            experiments.append(
                {
                    "experiment_id": f"E-hit-{cycle}",
                    "objective": "discriminate",
                    "paradigm": "A",
                    "entity_id": pair[0],
                    "action_value": pair[1],
                    "target_hypothesis_ids": [f"H-CQ{cycle + 1}"],
                }
            )
            used_pairs.add(pair)

        cursor = 0
        while len(experiments) < 10:
            # Enumerate a genuinely expanding 4x8 grid. The earlier correlated
            # modulo pair repeated after eight values and made this synthetic
            # fixture loop forever; that was a test-harness bug, not model logic.
            pair = (f"entity_{12 + ((cursor // 8) % 4):02d}", cursor % 8)
            cursor += 1
            if pair in used_pairs or pair == TARGETS[cycle]:
                continue
            used_pairs.add(pair)
            experiments.append(
                {
                    "experiment_id": f"E-fill-{cycle}-{len(experiments)}",
                    "objective": "discriminate",
                    "paradigm": "A",
                    "entity_id": pair[0],
                    "action_value": pair[1],
                    "target_hypothesis_ids": [f"H-CQ{cycle + 1}"],
                }
            )
        return {"experiments": experiments}


def test_critic_qualification_passes_when_any_cycle_reveals_injected_contradiction():
    backend = QualificationBackend(hit_cycle=1)
    result = run_critic_qualification(V1Critic(backend, "critic"))
    assert result.passes_safeguard
    assert [cycle.selected_revealing_intervention for cycle in result.cycles] == [False, True, False]
    assert result.consecutive_misses == 1
    assert len(backend.calls) == 3


def test_critic_qualification_fails_after_three_consecutive_eligible_misses():
    backend = QualificationBackend(hit_cycle=None)
    result = run_critic_qualification(V1Critic(backend, "critic"))
    assert not result.passes_safeguard
    assert result.consecutive_misses == 3
    assert all(not cycle.selected_revealing_intervention for cycle in result.cycles)


def test_trusted_qualification_answers_never_enter_critic_payload():
    fixtures = load_fixtures()
    for index, cycle in enumerate(fixtures["cycles"]):
        payload = _agent_payload(cycle, index)
        serialized = json.dumps(payload, sort_keys=True)
        assert "trusted_" not in serialized
        expected = cycle["trusted_expected_revealing_intervention"]
        assert expected not in payload.values()
