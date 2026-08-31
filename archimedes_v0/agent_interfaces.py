from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from .agent_protocol import ACommitDecision, BCommitDecision, CandidateSet, ExperimentBatch


class AgentInterfaceError(RuntimeError):
    pass


class StatelessJSONBackend(Protocol):
    """Provider adapter contract.

    Each invocation must create a fresh inference request. Implementations may not
    carry conversation/session identifiers or hidden message history between calls.
    """

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
        raise AgentInterfaceError(f"{role} returned schema-invalid JSON: {exc}") from exc


class StatelessConjecturer:
    def __init__(self, backend: StatelessJSONBackend, system_prompt: str, *, max_output_tokens: int = 4096):
        self._backend = backend
        self._system_prompt = system_prompt
        self._max_output_tokens = max_output_tokens

    def propose_candidates(self, payload: dict[str, Any]) -> CandidateSet:
        return _invoke_validated(
            self._backend,
            role="conjecturer",
            system_prompt=self._system_prompt,
            payload=payload,
            response_model=CandidateSet,
            max_output_tokens=self._max_output_tokens,
        )

    def decide_a(self, payload: dict[str, Any]) -> ACommitDecision:
        return _invoke_validated(
            self._backend,
            role="conjecturer",
            system_prompt=self._system_prompt,
            payload=payload,
            response_model=ACommitDecision,
            max_output_tokens=self._max_output_tokens,
        )

    def decide_b(self, payload: dict[str, Any]) -> BCommitDecision:
        return _invoke_validated(
            self._backend,
            role="conjecturer",
            system_prompt=self._system_prompt,
            payload=payload,
            response_model=BCommitDecision,
            max_output_tokens=self._max_output_tokens,
        )


class StatelessCritic:
    def __init__(self, backend: StatelessJSONBackend, system_prompt: str, *, max_output_tokens: int = 2048):
        self._backend = backend
        self._system_prompt = system_prompt
        self._max_output_tokens = max_output_tokens

    def propose_experiments(self, payload: dict[str, Any]) -> ExperimentBatch:
        return _invoke_validated(
            self._backend,
            role="critic",
            system_prompt=self._system_prompt,
            payload=payload,
            response_model=ExperimentBatch,
            max_output_tokens=self._max_output_tokens,
        )


class StatelessFlatAgent:
    """Single-role compute-matched Flat baseline interface.

    Every research round has two fresh calls under the same Flat system prompt:
    Generate (CandidateSet, 4096 max output tokens) and Select (ExperimentBatch,
    2048). Commit calls use 4096. The second slot is not given the Critic prompt.
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
        self._backend = backend
        self._system_prompt = system_prompt
        self._generate_max_output_tokens = generate_max_output_tokens
        self._select_max_output_tokens = select_max_output_tokens
        self._commit_max_output_tokens = commit_max_output_tokens

    def propose_candidates(self, payload: dict[str, Any]) -> CandidateSet:
        return _invoke_validated(
            self._backend,
            role="flat",
            system_prompt=self._system_prompt,
            payload=payload,
            response_model=CandidateSet,
            max_output_tokens=self._generate_max_output_tokens,
        )

    def propose_experiments(self, payload: dict[str, Any]) -> ExperimentBatch:
        return _invoke_validated(
            self._backend,
            role="flat",
            system_prompt=self._system_prompt,
            payload=payload,
            response_model=ExperimentBatch,
            max_output_tokens=self._select_max_output_tokens,
        )

    def decide_a(self, payload: dict[str, Any]) -> ACommitDecision:
        return _invoke_validated(
            self._backend,
            role="flat",
            system_prompt=self._system_prompt,
            payload=payload,
            response_model=ACommitDecision,
            max_output_tokens=self._commit_max_output_tokens,
        )

    def decide_b(self, payload: dict[str, Any]) -> BCommitDecision:
        return _invoke_validated(
            self._backend,
            role="flat",
            system_prompt=self._system_prompt,
            payload=payload,
            response_model=BCommitDecision,
            max_output_tokens=self._commit_max_output_tokens,
        )
