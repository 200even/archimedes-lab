from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from .v1_protocol import AExperimentBatch, CandidatePartitionSet


class V1AgentInterfaceError(RuntimeError):
    pass


class StatelessJSONBackend(Protocol):
    def invoke(
        self,
        *,
        role: str,
        system_prompt: str,
        payload: dict[str, Any],
        response_schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        ...


T = TypeVar("T", bound=BaseModel)


@lru_cache(maxsize=1)
def _authorized_agent_schemas() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "V1_SCHEMA_FREEZE.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("status") != "FROZEN_FOR_REFEREE_REVIEW_NOT_IMPLEMENTED":
        raise V1AgentInterfaceError("unexpected V1 schema-freeze status")
    return raw["agent_facing"]


def _rewrite_refs(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _rewrite_refs(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_refs(item) for item in value]
    if isinstance(value, str) and value.startswith("#/agent_facing/"):
        return "#/$defs/" + value.split("/")[-1]
    return value


def authorized_response_schema(schema_name: str) -> dict[str, Any]:
    schemas = _authorized_agent_schemas()
    if schema_name not in schemas:
        raise V1AgentInterfaceError(f"unknown frozen V1 schema {schema_name}")
    # Provider-facing schema is the exact authorized schema, with references moved
    # under standard JSON-Schema $defs without changing constraints.
    defs = {name: _rewrite_refs(schema) for name, schema in schemas.items()}
    return {"$ref": f"#/$defs/{schema_name}", "$defs": defs}


def _invoke_raw(
    backend: StatelessJSONBackend,
    *,
    role: str,
    system_prompt: str,
    payload: dict[str, Any],
    frozen_schema_name: str,
    max_output_tokens: int,
) -> dict[str, Any]:
    raw = backend.invoke(
        role=role,
        system_prompt=system_prompt,
        payload=payload,
        response_schema=authorized_response_schema(frozen_schema_name),
        max_output_tokens=max_output_tokens,
    )
    if not isinstance(raw, dict):
        raise V1AgentInterfaceError(f"{role} returned non-object structured output")
    return raw


def _invoke_validated(
    backend: StatelessJSONBackend,
    *,
    role: str,
    system_prompt: str,
    payload: dict[str, Any],
    response_model: type[T],
    frozen_schema_name: str,
    max_output_tokens: int,
) -> T:
    raw = _invoke_raw(
        backend,
        role=role,
        system_prompt=system_prompt,
        payload=payload,
        frozen_schema_name=frozen_schema_name,
        max_output_tokens=max_output_tokens,
    )
    try:
        return response_model.model_validate(raw)
    except ValidationError as exc:
        raise V1AgentInterfaceError(f"{role} returned schema-invalid JSON: {exc}") from exc


class V1Conjecturer:
    def __init__(self, backend: StatelessJSONBackend, system_prompt: str, *, max_output_tokens: int = 4096):
        self._backend = backend
        self._prompt = system_prompt
        self._max_output_tokens = max_output_tokens

    def propose(self, payload: dict[str, Any]) -> CandidatePartitionSet:
        return _invoke_validated(
            self._backend,
            role="conjecturer",
            system_prompt=self._prompt,
            payload=payload,
            response_model=CandidatePartitionSet,
            frozen_schema_name="CandidatePartitionSet",
            max_output_tokens=self._max_output_tokens,
        )

    def commit(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return raw structured commit JSON so the Broker charges before validation.

        The provider still receives the exact frozen ACommitDecision schema. The
        trusted Broker, not this role adapter, performs semantic validation after
        inspecting the top-level decision and charging the four-unit A gate for a
        stated commit. This preserves the preregistered resource firewall.
        """
        return _invoke_raw(
            self._backend,
            role="conjecturer",
            system_prompt=self._prompt,
            payload=payload,
            frozen_schema_name="ACommitDecision",
            max_output_tokens=self._max_output_tokens,
        )


class V1Critic:
    def __init__(self, backend: StatelessJSONBackend, system_prompt: str, *, max_output_tokens: int = 2048):
        self._backend = backend
        self._prompt = system_prompt
        self._max_output_tokens = max_output_tokens

    def select(self, payload: dict[str, Any]) -> AExperimentBatch:
        return _invoke_validated(
            self._backend,
            role="critic",
            system_prompt=self._prompt,
            payload=payload,
            response_model=AExperimentBatch,
            frozen_schema_name="AExperimentBatch",
            max_output_tokens=self._max_output_tokens,
        )


class V1FlatAgent:
    def __init__(
        self,
        backend: StatelessJSONBackend,
        system_prompt: str,
        *,
        generate_max_output_tokens: int = 4096,
        select_max_output_tokens: int = 2048,
        commit_max_output_tokens: int = 4096,
    ):
        self._backend = backend
        self._prompt = system_prompt
        self._generate_max_output_tokens = generate_max_output_tokens
        self._select_max_output_tokens = select_max_output_tokens
        self._commit_max_output_tokens = commit_max_output_tokens

    def generate(self, payload: dict[str, Any]) -> CandidatePartitionSet:
        return _invoke_validated(
            self._backend,
            role="flat",
            system_prompt=self._prompt,
            payload=payload,
            response_model=CandidatePartitionSet,
            frozen_schema_name="CandidatePartitionSet",
            max_output_tokens=self._generate_max_output_tokens,
        )

    def select(self, payload: dict[str, Any]) -> AExperimentBatch:
        return _invoke_validated(
            self._backend,
            role="flat",
            system_prompt=self._prompt,
            payload=payload,
            response_model=AExperimentBatch,
            frozen_schema_name="AExperimentBatch",
            max_output_tokens=self._select_max_output_tokens,
        )

    def commit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _invoke_raw(
            self._backend,
            role="flat",
            system_prompt=self._prompt,
            payload=payload,
            frozen_schema_name="ACommitDecision",
            max_output_tokens=self._commit_max_output_tokens,
        )
