from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from .v1_protocol import ACommitDecision, AExperimentBatch, CandidatePartitionSet


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


def _invoke_validated(
    backend: StatelessJSONBackend,
    *,
    role: str,
    system_prompt: str,
    payload: dict[str, Any],
    response_model: type[T],
    max_output_tokens: int,
) -> T:
    raw = backend.invoke(
        role=role,
        system_prompt=system_prompt,
        payload=payload,
        response_schema=response_model.model_json_schema(),
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
            max_output_tokens=self._max_output_tokens,
        )

    def commit(self, payload: dict[str, Any]) -> ACommitDecision:
        return _invoke_validated(
            self._backend,
            role="conjecturer",
            system_prompt=self._prompt,
            payload=payload,
            response_model=ACommitDecision,
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
            max_output_tokens=self._generate_max_output_tokens,
        )

    def select(self, payload: dict[str, Any]) -> AExperimentBatch:
        return _invoke_validated(
            self._backend,
            role="flat",
            system_prompt=self._prompt,
            payload=payload,
            response_model=AExperimentBatch,
            max_output_tokens=self._select_max_output_tokens,
        )

    def commit(self, payload: dict[str, Any]) -> ACommitDecision:
        return _invoke_validated(
            self._backend,
            role="flat",
            system_prompt=self._prompt,
            payload=payload,
            response_model=ACommitDecision,
            max_output_tokens=self._commit_max_output_tokens,
        )
