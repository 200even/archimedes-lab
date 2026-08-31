from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from .constants import DOMAIN_SIZE, BIT_WIDTH, MAX_EXPRESSION_DEPTH

MASK = DOMAIN_SIZE - 1

def rotl(v: int, shift: int) -> int:
    shift %= BIT_WIDTH
    return ((v << shift) & MASK) | (v >> (BIT_WIDTH - shift))

@dataclass(frozen=True)
class Program:
    """Hidden causal program. Serialized only in the sealed ground-truth file."""
    template: str
    params: dict[str, Any]

    @property
    def paradigm(self) -> str:
        return self.template[0]

    def operator_families(self) -> set[str]:
        if self.template.startswith("A"):
            return {"modular_arithmetic", "permutation"}
        return {"bitwise", "permutation"}

    def depth(self) -> int:
        # All frozen V0 templates have depth 4 or 5 by construction.
        return {"A1": 6, "A2": 4, "B1": 4, "B2": 5}[self.template]

    def evaluate(self, q: int, action: int) -> int:
        p = self.params
        if self.template == "A1":
            # P_A( q + (2q+1)*(a*x + c1) + c2 mod 8 )
            # (2q+1) is always odd, so every q retains action sensitivity;
            # the additive q term keeps all eight q response signatures distinct.
            z = (p["a"] * action + p["c1"]) % DOMAIN_SIZE
            z = (q + (2 * q + 1) * z + p["c2"]) % DOMAIN_SIZE
            return p["perm"][z]
        if self.template == "A2":
            # P_A( q + a*x + c1 mod 8 )
            z = (q + p["a"] * action + p["c1"]) % DOMAIN_SIZE
            return p["perm"][z]
        if self.template == "B1":
            # P_B( rotl(q,r) XOR rotl(u,s) )
            z = rotl(q, p["r"]) ^ rotl(action, p["s"])
            return p["perm"][z]
        if self.template == "B2":
            # P_B( rotl(q XOR c1,r) XOR (u XOR c2) )
            z = rotl(q ^ p["c1"], p["r"]) ^ (action ^ p["c2"])
            return p["perm"][z]
        raise ValueError(f"unknown template {self.template}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assert_grammar_invariants(program: Program) -> None:
    if program.depth() > MAX_EXPRESSION_DEPTH:
        raise AssertionError("program exceeds frozen expression-depth limit")
    if program.template.startswith("A") and program.operator_families() != {"modular_arithmetic", "permutation"}:
        raise AssertionError("Paradigm A family drift")
    if program.template.startswith("B") and program.operator_families() != {"bitwise", "permutation"}:
        raise AssertionError("Paradigm B family drift")
