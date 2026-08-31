from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from .ast_schema import (
    AbsDiffExpr,
    AddModExpr,
    BitAndExpr,
    BitOrExpr,
    ConstExpr,
    EqMaskExpr,
    MaxU3Expr,
    MinU3Expr,
    MulModExpr,
    PermutationExpr,
    ProgramSpec,
    RotlExpr,
    TheoryAST,
    VarExpr,
    XorExpr,
)
from .constants import DOMAIN_SIZE, MAX_EXPRESSION_DEPTH
from .theory_eval import operator_signature, program_for, variables_used


SYNTHESIZER_VERSION = "EnumerativeSynthesizer-V0.1"
_BINARY_KINDS = (
    "add_mod",
    "mul_mod",
    "xor",
    "bit_and",
    "bit_or",
    "min_u3",
    "max_u3",
    "abs_diff",
    "eq_mask",
)


@dataclass(frozen=True)
class ProgramObservation:
    q: int
    action: int
    y: int


@dataclass(frozen=True)
class ProgramCandidate:
    expression: object
    truth_table: tuple[int, ...]
    correct: int
    total: int
    exact_accuracy: float
    node_count: int
    depth: int
    canonical_ast: str


@dataclass(frozen=True)
class ProgramSearchResult:
    candidates: tuple[ProgramCandidate, ...]
    semantic_expressions_inspected: int
    beam_width: int
    search_ceiling: int


@dataclass
class _Node:
    expression: object
    signature: bytes
    correct: int
    node_count: int
    depth: int
    canonical: str

    @property
    def errors(self) -> int:
        return self.total - self.correct

    @property
    def total(self) -> int:
        return len(self._observations) if hasattr(self, "_observations") else 0


class CandidateSynthesizer(Protocol):
    """Visible-data-only law fitting shared identically by Full and Flat.

    Candidate latent cardinalities and entity assignments must arrive from the LLM.
    A synthesizer may fit only the executable program conditional on those supplied
    assignments; it may never search, merge, split, or modify the entity partition.
    """

    def synthesize(
        self,
        *,
        paradigm: str,
        observations: tuple[dict, ...],
        candidate_theories: tuple[TheoryAST, ...],
        frozen_a_theory: TheoryAST | None,
        limit: int = 32,
    ) -> tuple[TheoryAST, ...]:
        ...


def _canonical(expression: object) -> str:
    return json.dumps(expression.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _node_count(expression: object) -> int:
    kind = expression.kind
    if kind in {"var", "const"}:
        return 1
    if kind in {"rotl", "permute"}:
        return 1 + _node_count(expression.value)
    return 1 + _node_count(expression.left) + _node_count(expression.right)


def _expression_depth(expression: object) -> int:
    kind = expression.kind
    if kind in {"var", "const"}:
        return 1
    if kind in {"rotl", "permute"}:
        return 1 + _expression_depth(expression.value)
    return 1 + max(_expression_depth(expression.left), _expression_depth(expression.right))


def _rotl(value: int, shift: int) -> int:
    return ((value << shift) | (value >> (3 - shift))) & 7


def _apply_binary(kind: str, left: bytes, right: bytes) -> bytes:
    if kind == "add_mod":
        return bytes((a + b) % 8 for a, b in zip(left, right, strict=True))
    if kind == "mul_mod":
        return bytes((a * b) % 8 for a, b in zip(left, right, strict=True))
    if kind == "xor":
        return bytes(a ^ b for a, b in zip(left, right, strict=True))
    if kind == "bit_and":
        return bytes(a & b for a, b in zip(left, right, strict=True))
    if kind == "bit_or":
        return bytes(a | b for a, b in zip(left, right, strict=True))
    if kind == "min_u3":
        return bytes(min(a, b) for a, b in zip(left, right, strict=True))
    if kind == "max_u3":
        return bytes(max(a, b) for a, b in zip(left, right, strict=True))
    if kind == "abs_diff":
        return bytes(abs(a - b) for a, b in zip(left, right, strict=True))
    if kind == "eq_mask":
        return bytes(7 if a == b else 0 for a, b in zip(left, right, strict=True))
    raise ValueError(f"unsupported binary operator {kind}")


def _binary_expression(kind: str, left: object, right: object):
    constructors = {
        "add_mod": AddModExpr,
        "mul_mod": MulModExpr,
        "xor": XorExpr,
        "bit_and": BitAndExpr,
        "bit_or": BitOrExpr,
        "min_u3": MinU3Expr,
        "max_u3": MaxU3Expr,
        "abs_diff": AbsDiffExpr,
        "eq_mask": EqMaskExpr,
    }
    return constructors[kind](left=left, right=right)


def _best_permutation(signature: bytes, observations: tuple[tuple[int, int], ...]) -> tuple[int, ...]:
    """Exact maximum-agreement output bijection with lexicographic tie-breaking."""

    weights = [[0 for _ in range(DOMAIN_SIZE)] for _ in range(DOMAIN_SIZE)]
    for index, y in observations:
        weights[signature[index]][y] += 1

    @lru_cache(maxsize=None)
    def solve(row: int, mask: int) -> tuple[int, tuple[int, ...]]:
        if row == DOMAIN_SIZE:
            return 0, ()
        best_score = -1
        best_mapping: tuple[int, ...] | None = None
        for target in range(DOMAIN_SIZE):
            if mask & (1 << target):
                continue
            suffix_score, suffix = solve(row + 1, mask | (1 << target))
            score = weights[row][target] + suffix_score
            mapping = (target,) + suffix
            if score > best_score or (score == best_score and (best_mapping is None or mapping < best_mapping)):
                best_score = score
                best_mapping = mapping
        assert best_mapping is not None
        return best_score, best_mapping

    return solve(0, 0)[1]


class EnumerativeProgramSearch:
    """Deterministic bounded bottom-up semantic enumerator.

    The only qualification-tuned capacity parameter is `search_ceiling`. Beam width
    is a deterministic function of that ceiling, operator count, and max depth.
    Semantic duplicates are collapsed by complete finite truth table before they
    consume additional search capacity.

    `permute` is represented by the exact best visible-data output bijection for
    each inspected child rather than by expanding all 8! mappings. This is a
    deterministic algebraic optimization, not latent-partition search.
    """

    def __init__(self, *, search_ceiling: int, max_depth: int = MAX_EXPRESSION_DEPTH):
        if search_ceiling < 10:
            raise ValueError("search_ceiling must be at least 10")
        if max_depth < 1:
            raise ValueError("max_depth must be positive")
        self.search_ceiling = search_ceiling
        self.max_depth = max_depth

    def search(
        self,
        *,
        q_cardinality: int,
        latent_name: str,
        action_name: str,
        observations: tuple[ProgramObservation, ...],
        limit: int = 32,
    ) -> ProgramSearchResult:
        if not 1 <= q_cardinality <= DOMAIN_SIZE:
            raise ValueError("q_cardinality must fit the finite 3-bit domain")
        for obs in observations:
            if not 0 <= obs.q < q_cardinality:
                raise ValueError("observation q outside supplied cardinality")
            if not 0 <= obs.action < DOMAIN_SIZE or not 0 <= obs.y < DOMAIN_SIZE:
                raise ValueError("observation outside finite domain")

        table_size = q_cardinality * DOMAIN_SIZE
        indexed_observations = tuple((obs.q * DOMAIN_SIZE + obs.action, obs.y) for obs in observations)
        seen: dict[bytes, _Node] = {}
        inspected = 0

        def score(signature: bytes) -> int:
            return sum(signature[index] == y for index, y in indexed_observations)

        def add(expression: object, signature: bytes) -> _Node | None:
            nonlocal inspected
            if len(signature) != table_size:
                raise AssertionError("semantic signature length mismatch")
            node_count = _node_count(expression)
            depth = _expression_depth(expression)
            canonical = _canonical(expression)
            existing = seen.get(signature)
            if existing is not None:
                if (node_count, depth, canonical) < (existing.node_count, existing.depth, existing.canonical):
                    existing.expression = expression
                    existing.node_count = node_count
                    existing.depth = depth
                    existing.canonical = canonical
                return None
            if inspected >= self.search_ceiling:
                return None
            inspected += 1
            node = _Node(
                expression=expression,
                signature=signature,
                correct=score(signature),
                node_count=node_count,
                depth=depth,
                canonical=canonical,
            )
            seen[signature] = node
            return node

        points = tuple((q, action) for q in range(q_cardinality) for action in range(DOMAIN_SIZE))
        add(VarExpr(name=latent_name), bytes(q for q, _ in points))
        add(VarExpr(name=action_name), bytes(action for _, action in points))
        for value in range(DOMAIN_SIZE):
            add(ConstExpr(value=value), bytes([value]) * table_size)

        def add_best_permutation(node: _Node) -> None:
            if node.depth >= self.max_depth or inspected >= self.search_ceiling:
                return
            mapping = _best_permutation(node.signature, indexed_observations)
            if mapping == tuple(range(DOMAIN_SIZE)):
                return
            signature = bytes(mapping[value] for value in node.signature)
            add(PermutationExpr(value=node.expression, mapping=list(mapping)), signature)

        for node in tuple(seen.values()):
            add_best_permutation(node)

        beam_width = max(
            4,
            math.isqrt(max(1, self.search_ceiling // (len(_BINARY_KINDS) * self.max_depth))),
        )

        for _ in range(2, self.max_depth + 1):
            if inspected >= self.search_ceiling:
                break
            ranked = sorted(
                seen.values(),
                key=lambda node: (-node.correct, node.node_count, node.depth, node.canonical),
            )
            beam = ranked[:beam_width]

            for node in beam:
                if inspected >= self.search_ceiling:
                    break
                if node.depth + 1 > self.max_depth:
                    continue
                for shift in (1, 2):
                    signature = bytes(_rotl(value, shift) for value in node.signature)
                    added = add(RotlExpr(value=node.expression, shift=shift), signature)
                    if added is not None:
                        add_best_permutation(added)
                    if inspected >= self.search_ceiling:
                        break
                add_best_permutation(node)

            for kind in _BINARY_KINDS:
                if inspected >= self.search_ceiling:
                    break
                for left in beam:
                    if inspected >= self.search_ceiling:
                        break
                    for right in beam:
                        if 1 + max(left.depth, right.depth) > self.max_depth:
                            continue
                        signature = _apply_binary(kind, left.signature, right.signature)
                        expression = _binary_expression(kind, left.expression, right.expression)
                        added = add(expression, signature)
                        if added is not None:
                            add_best_permutation(added)
                        if inspected >= self.search_ceiling:
                            break

        total = len(observations)
        ranked = sorted(
            seen.values(),
            key=lambda node: (-node.correct, node.node_count, node.depth, node.canonical),
        )
        candidates = tuple(
            ProgramCandidate(
                expression=node.expression,
                truth_table=tuple(node.signature),
                correct=node.correct,
                total=total,
                exact_accuracy=(node.correct / total) if total else 0.0,
                node_count=node.node_count,
                depth=node.depth,
                canonical_ast=node.canonical,
            )
            for node in ranked[:limit]
        )
        return ProgramSearchResult(
            candidates=candidates,
            semantic_expressions_inspected=inspected,
            beam_width=beam_width,
            search_ceiling=self.search_ceiling,
        )


class EnumerativeSynthesizer:
    """Fit laws conditional on LLM-supplied entity partitions; never search partitions."""

    def __init__(self, *, semantic_search_ceiling: int, max_depth: int = MAX_EXPRESSION_DEPTH):
        self.semantic_search_ceiling = semantic_search_ceiling
        self.max_depth = max_depth

    def synthesize(
        self,
        *,
        paradigm: str,
        observations: tuple[dict, ...],
        candidate_theories: tuple[TheoryAST, ...],
        frozen_a_theory: TheoryAST | None,
        limit: int = 32,
    ) -> tuple[TheoryAST, ...]:
        if paradigm not in {"A", "B"}:
            raise ValueError("paradigm must be A or B")
        if limit < 1:
            return ()

        action_name = "x" if paradigm == "A" else "u"
        ranked_outputs: list[tuple[tuple, TheoryAST]] = []
        source_count = max(1, len(candidate_theories))
        programs_per_source = max(1, math.ceil(limit / source_count))

        for source_index, source in enumerate(candidate_theories):
            if len(source.latent_variables) != 1:
                continue
            latent = source.latent_variables[0]

            if paradigm == "B":
                if frozen_a_theory is None or len(frozen_a_theory.latent_variables) != 1:
                    continue
                frozen_latent = frozen_a_theory.latent_variables[0]
                if latent.model_copy(update={"frozen": True}) != frozen_latent.model_copy(update={"frozen": True}):
                    continue
                latent = frozen_latent

            relevant = tuple(obs for obs in observations if obs.get("paradigm") == paradigm)
            program_observations: list[ProgramObservation] = []
            valid = True
            for obs in relevant:
                entity_id = obs["entity_id"]
                if entity_id not in latent.assignments:
                    valid = False
                    break
                program_observations.append(
                    ProgramObservation(
                        q=latent.assignments[entity_id],
                        action=obs["action_value"],
                        y=obs["y"],
                    )
                )
            if not valid or not program_observations:
                continue

            search = EnumerativeProgramSearch(
                search_ceiling=self.semantic_search_ceiling,
                max_depth=self.max_depth,
            ).search(
                q_cardinality=latent.cardinality,
                latent_name=latent.name,
                action_name=action_name,
                observations=tuple(program_observations),
                limit=max(programs_per_source * 4, programs_per_source),
            )

            accepted = 0
            for program_index, candidate in enumerate(search.candidates):
                used = variables_used(candidate.expression)
                if latent.name not in used or action_name not in used:
                    continue
                if not operator_signature(candidate.expression):
                    continue

                if paradigm == "A":
                    programs = [ProgramSpec(paradigm="A", expression=candidate.expression)]
                else:
                    assert frozen_a_theory is not None
                    programs = [
                        program_for(frozen_a_theory, "A"),
                        ProgramSpec(paradigm="B", expression=candidate.expression),
                    ]

                ephemeral_id = f"T-SYN-{paradigm}-{source_index:02d}-{program_index:02d}"
                theory = source.model_copy(
                    update={
                        "theory_id": ephemeral_id,
                        "latent_variables": [latent],
                        "programs": programs,
                        "status": "candidate",
                        "evidence_experiment_ids": [],
                    }
                )
                rank_key = (
                    -candidate.correct,
                    candidate.node_count,
                    candidate.depth,
                    candidate.canonical_ast,
                    source_index,
                    program_index,
                )
                ranked_outputs.append((rank_key, theory))
                accepted += 1
                if accepted >= programs_per_source:
                    break

        ranked_outputs.sort(key=lambda item: item[0])
        return tuple(theory for _, theory in ranked_outputs[:limit])


class NoSynthesis:
    """Development-only no-op implementation. Not authorized for comparative runs."""

    def synthesize(
        self,
        *,
        paradigm: str,
        observations: tuple[dict, ...],
        candidate_theories: tuple[TheoryAST, ...],
        frozen_a_theory: TheoryAST | None,
        limit: int = 32,
    ) -> tuple[TheoryAST, ...]:
        return tuple(candidate_theories[:limit])
