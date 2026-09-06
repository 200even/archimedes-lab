from __future__ import annotations

from typing import Any

from .v1_agent_interfaces import StatelessJSONBackend, V1FlatAgent, V1AgentInterfaceError
from .v1_protocol import AExperimentBatch
from .v1_v11_critic import V11RawAExperimentBatch, v11_critic_provider_schema


def canonical_benchmark_experiment_id(round_index: int, position: int) -> str:
    """Trusted bookkeeping ID for V1.1 benchmark intervention batches.

    The identifier depends only on public round index and provider array position.
    It cannot encode entity/action content, condition, world identity, outcomes, or
    any hidden-world information.
    """
    if type(round_index) is not int or not 0 <= round_index < 6:
        raise ValueError("V1.1 benchmark round_index must be 0..5")
    if type(position) is not int or not 0 <= position < 10:
        raise ValueError("V1.1 benchmark position must be 0..9")
    return f"E-R{round_index + 1:02d}-{position + 1:02d}"


def inject_benchmark_experiment_ids(
    raw_batch: V11RawAExperimentBatch,
    *,
    round_index: int,
) -> AExperimentBatch:
    rows: list[dict[str, Any]] = []
    for position, experiment in enumerate(raw_batch.experiments):
        meaningful = experiment.model_dump(mode="json")
        rows.append(
            {
                "experiment_id": canonical_benchmark_experiment_id(round_index, position),
                **meaningful,
            }
        )
    return AExperimentBatch.model_validate({"experiments": rows})


class V11BenchmarkSelector:
    """Provider-facing selector with trusted non-semantic ID assignment.

    Used identically for Full/Critic and Flat/Select. This preserves the V1.1
    interface correction while preventing bookkeeping syntax from becoming an
    arm-specific confound.
    """

    def __init__(
        self,
        backend: StatelessJSONBackend,
        system_prompt: str,
        *,
        role: str,
        max_output_tokens: int = 2048,
    ):
        if role not in {"critic", "flat"}:
            raise ValueError("V1.1 benchmark selector role must be critic or flat")
        self._backend = backend
        self._prompt = system_prompt
        self._role = role
        self._max_output_tokens = max_output_tokens

    def select(self, payload: dict[str, Any]) -> AExperimentBatch:
        round_index = payload.get("round_index")
        if type(round_index) is not int:
            raise V1AgentInterfaceError("V1.1 benchmark selector requires integer round_index")
        raw = self._backend.invoke(
            role=self._role,
            system_prompt=self._prompt,
            payload=payload,
            response_schema=v11_critic_provider_schema(),
            max_output_tokens=self._max_output_tokens,
        )
        if not isinstance(raw, dict):
            raise V1AgentInterfaceError(f"{self._role} returned non-object structured output")
        try:
            raw_batch = V11RawAExperimentBatch.model_validate(raw)
            return inject_benchmark_experiment_ids(raw_batch, round_index=round_index)
        except Exception as exc:
            # Preserve the existing interface distinction: semantic/schema output
            # failures are not provider infrastructure failures and receive no retry.
            if isinstance(exc, V1AgentInterfaceError):
                raise
            raise V1AgentInterfaceError(f"{self._role} returned schema-invalid JSON: {exc}") from exc


class V11FlatAgent:
    """V1 Flat agent with the V1.1 bookkeeping correction on Select only.

    Generate and commit are byte-for-byte the existing V1 Flat interface. Select
    uses the same Flat prompt/role and provider settings, but model-generated
    experiment IDs are removed and trusted IDs are injected after validation of
    every scientifically meaningful intervention field.
    """

    def __init__(
        self,
        backend: StatelessJSONBackend,
        system_prompt: str,
        *,
        generate_max_output_tokens: int = 4096,
        select_max_output_tokens: int = 2048,
        commit_max_output_tokens: int = 4096,
    ):
        self._legacy = V1FlatAgent(
            backend,
            system_prompt,
            generate_max_output_tokens=generate_max_output_tokens,
            select_max_output_tokens=select_max_output_tokens,
            commit_max_output_tokens=commit_max_output_tokens,
        )
        self._selector = V11BenchmarkSelector(
            backend,
            system_prompt,
            role="flat",
            max_output_tokens=select_max_output_tokens,
        )

    def generate(self, payload: dict[str, Any]):
        return self._legacy.generate(payload)

    def select(self, payload: dict[str, Any]) -> AExperimentBatch:
        return self._selector.select(payload)

    def commit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._legacy.commit(payload)
