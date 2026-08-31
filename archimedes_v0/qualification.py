from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass

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
    RotlExpr,
    VarExpr,
    XorExpr,
)
from .theory_eval import expression_depth


QUALIFICATION_CORPUS_SIZE = 1000
QUALIFICATION_MAX_DEPTH = 5
QUALIFICATION_SEED = "archimedes-v0-qualification-20260831"
QUALIFICATION_EXPECTED_DIGEST = "e5a643f5b7bf4c9c69297108a9ad4fa29569ca52152de40a2449b98e9c998400"

_BINARY_CONSTRUCTORS = (
    ("add_mod", AddModExpr),
    ("mul_mod", MulModExpr),
    ("xor", XorExpr),
    ("bit_and", BitAndExpr),
    ("bit_or", BitOrExpr),
    ("min_u3", MinU3Expr),
    ("max_u3", MaxU3Expr),
    ("abs_diff", AbsDiffExpr),
    ("eq_mask", EqMaskExpr),
)
_PERMUTATION_COUNT = math.factorial(8)


@dataclass(frozen=True)
class QualificationCorpusStats:
    count: int
    digest_sha256: str
    depth_counts: dict[int, int]
    root_kind_counts: dict[str, int]
    operator_counts: dict[str, int]


def qualification_tree_counts(max_depth: int = QUALIFICATION_MAX_DEPTH) -> dict[int, int]:
    """Exact counts of complete syntax trees of depth <= d in the frozen G_Q grammar.

    Leaves have depth 1. Ordered binary children are distinct syntax trees. Every
    concrete 8-symbol permutation is a distinct AST, as required by the accepted
    uniform-canonical-tree qualification definition.
    """

    if max_depth < 1:
        raise ValueError("max_depth must be >= 1")
    counts = {1: 10}  # q, a, and constants 0..7
    for depth in range(2, max_depth + 1):
        child_count = counts[depth - 1]
        unary_count = (2 + _PERMUTATION_COUNT) * child_count
        binary_count = len(_BINARY_CONSTRUCTORS) * child_count * child_count
        counts[depth] = 10 + unary_count + binary_count
    return counts


def _unrank_permutation(rank: int) -> list[int]:
    if not 0 <= rank < _PERMUTATION_COUNT:
        raise ValueError("permutation rank out of range")
    remaining = list(range(8))
    result: list[int] = []
    for width in range(8, 0, -1):
        factor = math.factorial(width - 1)
        index, rank = divmod(rank, factor)
        result.append(remaining.pop(index))
    return result


def unrank_qualification_expr(max_depth: int, rank: int):
    """Map one integer bijectively to one canonical G_Q syntax tree."""

    counts = qualification_tree_counts(max_depth)
    total = counts[max_depth]
    if not 0 <= rank < total:
        raise ValueError("tree rank out of range")

    if rank < 10:
        if rank == 0:
            return VarExpr(name="q")
        if rank == 1:
            return VarExpr(name="a")
        return ConstExpr(value=rank - 2)
    if max_depth == 1:
        raise AssertionError("non-leaf rank at depth 1")

    rank -= 10
    child_count = counts[max_depth - 1]

    rotl_span = 2 * child_count
    if rank < rotl_span:
        shift_index, child_rank = divmod(rank, child_count)
        return RotlExpr(value=unrank_qualification_expr(max_depth - 1, child_rank), shift=shift_index + 1)
    rank -= rotl_span

    permutation_span = _PERMUTATION_COUNT * child_count
    if rank < permutation_span:
        permutation_rank, child_rank = divmod(rank, child_count)
        return PermutationExpr(
            value=unrank_qualification_expr(max_depth - 1, child_rank),
            mapping=_unrank_permutation(permutation_rank),
        )
    rank -= permutation_span

    pair_count = child_count * child_count
    constructor_index, within_constructor = divmod(rank, pair_count)
    _, constructor = _BINARY_CONSTRUCTORS[constructor_index]
    left_rank, right_rank = divmod(within_constructor, child_count)
    return constructor(
        left=unrank_qualification_expr(max_depth - 1, left_rank),
        right=unrank_qualification_expr(max_depth - 1, right_rank),
    )


def _uniform_rank(*, seed: str, sample_index: int, modulus: int) -> int:
    """Version-stable SHA-256 rejection sampler over [0, modulus)."""

    if modulus <= 0:
        raise ValueError("modulus must be positive")
    byte_width = (modulus.bit_length() + 7) // 8
    sample_space = 1 << (8 * byte_width)
    acceptance_limit = sample_space - (sample_space % modulus)

    attempt = 0
    while True:
        raw = bytearray()
        block = 0
        while len(raw) < byte_width:
            payload = f"{seed}|{sample_index}|{attempt}|{block}".encode("utf-8")
            raw.extend(hashlib.sha256(payload).digest())
            block += 1
        value = int.from_bytes(raw[:byte_width], "big")
        if value < acceptance_limit:
            return value % modulus
        attempt += 1


def generate_qualification_corpus(
    *,
    count: int = QUALIFICATION_CORPUS_SIZE,
    seed: str = QUALIFICATION_SEED,
    max_depth: int = QUALIFICATION_MAX_DEPTH,
):
    """Generate the frozen benchmark-independent uniform syntax-tree corpus."""

    total = qualification_tree_counts(max_depth)[max_depth]
    return tuple(
        unrank_qualification_expr(max_depth, _uniform_rank(seed=seed, sample_index=i, modulus=total))
        for i in range(count)
    )


def qualification_corpus_digest(corpus) -> str:
    payload = json.dumps(
        [expr.model_dump(mode="json") for expr in corpus],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _walk_kinds(expr):
    yield expr.kind
    if expr.kind in {"rotl", "permute"}:
        yield from _walk_kinds(expr.value)
    elif expr.kind not in {"var", "const"}:
        yield from _walk_kinds(expr.left)
        yield from _walk_kinds(expr.right)


def qualification_corpus_stats(corpus) -> QualificationCorpusStats:
    corpus = tuple(corpus)
    depth_counts = Counter(expression_depth(expr) for expr in corpus)
    root_counts = Counter(expr.kind for expr in corpus)
    operators: Counter[str] = Counter()
    for expr in corpus:
        operators.update(_walk_kinds(expr))
    return QualificationCorpusStats(
        count=len(corpus),
        digest_sha256=qualification_corpus_digest(corpus),
        depth_counts=dict(sorted(depth_counts.items())),
        root_kind_counts=dict(sorted(root_counts.items())),
        operator_counts=dict(sorted(operators.items())),
    )
