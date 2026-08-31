from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .ast_schema import TheoryAST
from .constants import DOMAIN_SIZE
from .theory_eval import TheoryEvaluationError, evaluate_expr, program_for


@dataclass(frozen=True)
class FunctionalMinimalityResult:
    paradigm: str
    declared_cardinality: int
    effective_cardinality: int
    functionally_minimal: bool
    redundant_groups: tuple[tuple[int, ...], ...]
    signature_digest: str


def functional_minimality(theory: TheoryAST, paradigm: str = "A") -> FunctionalMinimalityResult:
    """Detect redundant declared labels using the theory's complete response signatures.

    This diagnostic uses only the committed theory. It never reads generator ground
    truth or sealed observations. Two declared labels are redundant when the theory
    predicts the same output for every legal intervention value.
    """
    if len(theory.latent_variables) != 1:
        raise TheoryEvaluationError("functional minimality requires exactly one latent variable")
    latent = theory.latent_variables[0]
    program = program_for(theory, paradigm)
    action_name = "x" if paradigm == "A" else "u"

    signatures: dict[int, tuple[int, ...]] = {}
    for label in range(latent.cardinality):
        signatures[label] = tuple(
            evaluate_expr(program.expression, {latent.name: label, action_name: action})
            for action in range(DOMAIN_SIZE)
        )

    grouped: dict[tuple[int, ...], list[int]] = {}
    for label, signature in signatures.items():
        grouped.setdefault(signature, []).append(label)

    redundant = tuple(
        tuple(labels)
        for labels in sorted(grouped.values(), key=lambda values: tuple(values))
        if len(labels) > 1
    )
    payload = [[label, list(signatures[label])] for label in sorted(signatures)]
    digest = hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=False).encode()
    ).hexdigest()

    return FunctionalMinimalityResult(
        paradigm=paradigm,
        declared_cardinality=latent.cardinality,
        effective_cardinality=len(grouped),
        functionally_minimal=not redundant,
        redundant_groups=redundant,
        signature_digest=digest,
    )
