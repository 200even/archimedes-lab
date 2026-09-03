from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .v1_agent_interfaces import V1AgentInterfaceError, V1Critic
from .v1_critic_qualification import _agent_payload, load_fixtures
from .v1_gemini_backend import GeminiUsageRecord, InMemoryUsageSink, V1ProviderError


@dataclass(frozen=True)
class LiveCriticCycle:
    cycle_index: int
    cycle_id: str
    target_entity_id: str
    target_action_value: int
    selected_batch: dict[str, Any] | None
    selected_revealing_intervention: bool | None
    semantic_validation_error: str | None
    usage_index: int | None


@dataclass(frozen=True)
class LiveCriticExecution:
    fixture_set: str
    cycles: tuple[LiveCriticCycle, ...]
    consecutive_misses: int | None
    passes_safeguard: bool | None
    terminal_execution_class: str
    provider_failure: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_set": self.fixture_set,
            "cycles": [asdict(row) for row in self.cycles],
            "consecutive_misses": self.consecutive_misses,
            "passes_safeguard": self.passes_safeguard,
            "terminal_execution_class": self.terminal_execution_class,
            "provider_failure": self.provider_failure,
        }


def _pending_cycle(cycle: dict[str, Any], index: int) -> LiveCriticCycle:
    expected = cycle["trusted_expected_revealing_intervention"]
    return LiveCriticCycle(
        cycle_index=index,
        cycle_id=cycle["cycle_id"],
        target_entity_id=expected["entity_id"],
        target_action_value=expected["action_value"],
        selected_batch=None,
        selected_revealing_intervention=None,
        semantic_validation_error=None,
        usage_index=None,
    )


def execute_authorized_critic_safeguard(
    critic: V1Critic,
    usage_sink: InMemoryUsageSink,
) -> LiveCriticExecution:
    """Execute exactly the preregistered three-cycle Critic safeguard.

    A completed provider response that fails the normative V1 response validator is
    a miss for that cycle. It receives no retry, but the next preregistered cycle
    still runs. A provider/transport/protocol failure aborts immediately and later
    cycles are not called. This distinction preserves the accepted zero-retry rule
    while treating a completed but scientifically inadmissible selection as a model
    failure rather than infrastructure failure.
    """

    fixtures = load_fixtures()
    cycles = fixtures["cycles"]
    output: list[LiveCriticCycle] = []
    misses = 0

    for index, cycle in enumerate(cycles):
        expected = cycle["trusted_expected_revealing_intervention"]
        before_usage = len(usage_sink.records)
        try:
            batch = critic.select(_agent_payload(cycle, index))
        except V1ProviderError as exc:
            output.append(_pending_cycle(cycle, index))
            output.extend(_pending_cycle(cycles[j], j) for j in range(index + 1, len(cycles)))
            return LiveCriticExecution(
                fixture_set=fixtures["fixture_set"],
                cycles=tuple(output),
                consecutive_misses=None,
                passes_safeguard=None,
                terminal_execution_class="ABORTED_PROVIDER_INFRASTRUCTURE",
                provider_failure=f"{type(exc).__name__}: {exc}",
            )
        except V1AgentInterfaceError as exc:
            # GeminiUsageRecord is appended after a completed provider interaction
            # and before trusted Pydantic validation. If no record was appended,
            # the failure happened before a completed provider call and is treated
            # as an execution/protocol abort rather than a scientific miss.
            if len(usage_sink.records) != before_usage + 1:
                output.append(_pending_cycle(cycle, index))
                output.extend(_pending_cycle(cycles[j], j) for j in range(index + 1, len(cycles)))
                return LiveCriticExecution(
                    fixture_set=fixtures["fixture_set"],
                    cycles=tuple(output),
                    consecutive_misses=None,
                    passes_safeguard=None,
                    terminal_execution_class="ABORTED_PROVIDER_INFRASTRUCTURE",
                    provider_failure=f"local response-validation path failed before auditable completed usage: {exc}",
                )
            misses += 1
            output.append(
                LiveCriticCycle(
                    cycle_index=index,
                    cycle_id=cycle["cycle_id"],
                    target_entity_id=expected["entity_id"],
                    target_action_value=expected["action_value"],
                    selected_batch=None,
                    selected_revealing_intervention=False,
                    semantic_validation_error=str(exc),
                    usage_index=before_usage,
                )
            )
            continue

        if len(usage_sink.records) != before_usage + 1:
            raise RuntimeError("completed Critic call did not append exactly one trusted usage record")

        hit = any(
            experiment.entity_id == expected["entity_id"]
            and experiment.action_value == expected["action_value"]
            for experiment in batch.experiments
        )
        misses = 0 if hit else misses + 1
        output.append(
            LiveCriticCycle(
                cycle_index=index,
                cycle_id=cycle["cycle_id"],
                target_entity_id=expected["entity_id"],
                target_action_value=expected["action_value"],
                selected_batch=batch.model_dump(mode="json"),
                selected_revealing_intervention=hit,
                semantic_validation_error=None,
                usage_index=before_usage,
            )
        )

    passed = misses < 3
    return LiveCriticExecution(
        fixture_set=fixtures["fixture_set"],
        cycles=tuple(output),
        consecutive_misses=misses,
        passes_safeguard=passed,
        terminal_execution_class="COMPLETED_PASS" if passed else "COMPLETED_FAIL",
        provider_failure=None,
    )


def usage_for_cycle(cycle: LiveCriticCycle, records: list[GeminiUsageRecord]) -> GeminiUsageRecord | None:
    if cycle.usage_index is None:
        return None
    if cycle.usage_index < 0 or cycle.usage_index >= len(records):
        raise RuntimeError("qualification cycle references an invalid usage-record index")
    return records[cycle.usage_index]
