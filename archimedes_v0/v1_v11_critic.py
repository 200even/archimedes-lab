from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import Field, ValidationError, model_validator

from .v1_agent_interfaces import StatelessJSONBackend, V1AgentInterfaceError, authorized_response_schema
from .v1_protocol import AExperimentBatch, ENTITIES, StrictModel


class V11RawAInterventionProposal(StrictModel):
    objective: Literal["discriminate", "estimate"]
    paradigm: Literal["A"] = "A"
    entity_id: str
    action_value: int = Field(ge=0, le=7)
    target_hypothesis_ids: list[str] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_meaningful_fields(self):
        if self.entity_id not in ENTITIES:
            raise ValueError("unknown entity_id")
        if len(self.target_hypothesis_ids) != len(set(self.target_hypothesis_ids)):
            raise ValueError("target_hypothesis_ids must be unique")
        return self


class V11RawAExperimentBatch(StrictModel):
    experiments: list[V11RawAInterventionProposal] = Field(min_length=10, max_length=10)


def canonical_qualification_experiment_id(round_index: int, position: int) -> str:
    if type(round_index) is not int or round_index not in (0, 1, 2):
        raise ValueError("V1.1 qualification round_index must be 0, 1, or 2")
    if type(position) is not int or not 0 <= position < 10:
        raise ValueError("V1.1 qualification position must be 0..9")
    return f"E-CQ{round_index + 1}-{position + 1:02d}"


def inject_qualification_experiment_ids(
    raw_batch: V11RawAExperimentBatch,
    *,
    round_index: int,
) -> AExperimentBatch:
    rows: list[dict[str, Any]] = []
    for position, experiment in enumerate(raw_batch.experiments):
        meaningful = experiment.model_dump(mode="json")
        rows.append(
            {
                "experiment_id": canonical_qualification_experiment_id(round_index, position),
                **meaningful,
            }
        )
    return AExperimentBatch.model_validate({"experiments": rows})


def v11_critic_provider_schema() -> dict[str, Any]:
    schema = deepcopy(authorized_response_schema("AExperimentBatch"))
    try:
        item_schema = schema["properties"]["experiments"]["items"]
        properties = item_schema["properties"]
    except (KeyError, TypeError) as exc:
        raise V1AgentInterfaceError("unexpected projected AExperimentBatch schema shape") from exc

    if "experiment_id" not in properties:
        raise V1AgentInterfaceError("projected AExperimentBatch schema unexpectedly lacks experiment_id")
    del properties["experiment_id"]

    required = item_schema.get("required")
    if isinstance(required, list):
        item_schema["required"] = [name for name in required if name != "experiment_id"]

    item_schema["additionalProperties"] = False
    return schema


class V11Critic:
    def __init__(self, backend: StatelessJSONBackend, system_prompt: str, *, max_output_tokens: int = 2048):
        self._backend = backend
        self._prompt = system_prompt
        self._max_output_tokens = max_output_tokens

    def select(self, payload: dict[str, Any]) -> AExperimentBatch:
        round_index = payload.get("round_index")
        if type(round_index) is not int:
            raise V1AgentInterfaceError("V1.1 Critic payload requires integer round_index")

        raw = self._backend.invoke(
            role="critic",
            system_prompt=self._prompt,
            payload=payload,
            response_schema=v11_critic_provider_schema(),
            max_output_tokens=self._max_output_tokens,
        )
        if not isinstance(raw, dict):
            raise V1AgentInterfaceError("critic returned non-object structured output")
        try:
            raw_batch = V11RawAExperimentBatch.model_validate(raw)
            return inject_qualification_experiment_ids(raw_batch, round_index=round_index)
        except ValidationError as exc:
            raise V1AgentInterfaceError(f"critic returned schema-invalid JSON: {exc}") from exc
