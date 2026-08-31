from __future__ import annotations

from typing import Protocol

from .ast_schema import TheoryAST


class CandidateSynthesizer(Protocol):
    """Deterministic visible-data-only synthesis interface shared by all arms.

    The concrete implementation is intentionally not chosen by this interface.
    Before any benchmark exposure, the exact implementation/version and invocation
    schedule must be frozen identically for Archimedes-Full and Flat LLM+synthesis.
    """

    def synthesize(
        self,
        *,
        paradigm: str,
        observations: tuple[dict, ...],
        frozen_a_theory: TheoryAST | None,
        limit: int = 4,
    ) -> tuple[TheoryAST, ...]:
        ...


class NoSynthesis:
    """Test/development implementation. Not authorized for comparative runs."""

    def synthesize(
        self,
        *,
        paradigm: str,
        observations: tuple[dict, ...],
        frozen_a_theory: TheoryAST | None,
        limit: int = 4,
    ) -> tuple[TheoryAST, ...]:
        return ()
