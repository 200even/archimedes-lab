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


def _enum_type(values: list[Any]) -> str | None:
    if values and all(isinstance(value, str) for value in values):
        return "string"
    if values and all(type(value) is int for value in values):
        return "integer"
    return None


def _project_provider_schema(value: Any, *, schemas: dict[str, Any], stack: tuple[str, ...] = ()) -> Any:
    """Project the normative freeze to Gemini's documented JSON-Schema subset.

    Scientific/semantic validation remains the exact V1 freeze plus trusted
    Pydantic/Broker checks. This projection changes only which constraints are
    redundantly enforced by the provider's structured-output decoder:

    * internal refs are deterministically inlined;
    * `const` becomes equivalent one-value `enum`;
    * `oneOf` becomes `anyOf` (the V1 branches are type-disjoint);
    * provider-undocumented `pattern` and `uniqueItems` are omitted and retained
      exclusively as trusted post-response validation.

    No model output bypasses the trusted validators, so projection cannot widen
    the accepted scientific hypothesis class.
    """
    if isinstance(value, list):
        return [_project_provider_schema(item, schemas=schemas, stack=stack) for item in value]
    if not isinstance(value, dict):
        return value

    if "$ref" in value:
        ref = value["$ref"]
        prefix = "#/agent_facing/"
        if not isinstance(ref, str) or not ref.startswith(prefix):
            raise V1AgentInterfaceError(f"unsupported frozen-schema reference {ref!r}")
        name = ref[len(prefix) :]
        if name not in schemas or name in stack:
            raise V1AgentInterfaceError(f"invalid/cyclic frozen-schema reference {ref!r}")
        return _project_provider_schema(schemas[name], schemas=schemas, stack=stack + (name,))

    output: dict[str, Any] = {}
    if "const" in value:
        const_value = value["const"]
        output["enum"] = [const_value]
        inferred = _enum_type([const_value])
        if inferred is not None:
            output["type"] = inferred

    if "oneOf" in value:
        output["anyOf"] = _project_provider_schema(value["oneOf"], schemas=schemas, stack=stack)

    for key, item in value.items():
        if key in {"$ref", "const", "oneOf", "pattern", "uniqueItems"} or key.startswith("x-"):
            continue
        if key == "type" and item == "null":
            # Gemini's structured-output documentation describes nullable types
            # by including "null" in the type array.
            output[key] = ["null"]
            continue
        if key in {"properties"}:
            output[key] = {
                name: _project_provider_schema(schema, schemas=schemas, stack=stack)
                for name, schema in item.items()
            }
            continue
        if key in {"items", "anyOf"}:
            output[key] = _project_provider_schema(item, schemas=schemas, stack=stack)
            continue
        output[key] = item

    if "enum" in output and "type" not in output:
        inferred = _enum_type(output["enum"])
        if inferred is not None:
            output["type"] = inferred
    return output


def authorized_response_schema(schema_name: str) -> dict[str, Any]:
    schemas = _authorized_agent_schemas()
    if schema_name not in schemas:
        raise V1AgentInterfaceError(f"unknown frozen V1 schema {schema_name}")
    return _project_provider_schema(schemas[schema_name], schemas=schemas, stack=(schema_name,))


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

        The provider receives the deterministic Gemini-compatible projection of
        the frozen ACommitDecision schema. The trusted Broker performs the exact
        normative validation after inspecting the top-level decision and charging
        the four-unit A gate for a stated commit.
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
