from __future__ import annotations
import hashlib
import random
from typing import Any
from .constants import DOMAIN_SIZE
from .grammar import Program

class HiddenWorldRuntime:
    """Ground-truth runtime. This object belongs behind the Experiment Broker boundary."""
    def __init__(self, hidden_spec: dict[str, Any]):
        self.spec = hidden_spec
        self.kind = hidden_spec["world_kind"]
        self.noise_rate = float(hidden_spec["measurement_noise_rate"])
        self.noise_key = hidden_spec["measurement_noise_key"]
        if self.kind == "causal":
            self.q = hidden_spec["latent_q_by_entity"]
            self.programs = {
                "A": Program(**hidden_spec["program_a"]),
                "B": Program(**hidden_spec["program_b"]),
            }

    def _rng_for(self, paradigm: str, entity: str, action: int, repetition: int, channel: str) -> random.Random:
        token = f"{self.noise_key}|{channel}|{paradigm}|{entity}|{action}|{repetition}"
        digest = hashlib.sha256(token.encode()).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    def noiseless(self, paradigm: str, entity: str, action: int) -> int:
        if self.kind != "causal":
            raise RuntimeError("Null World has no noiseless causal value")
        return self.programs[paradigm].evaluate(self.q[entity], action)

    def observe(self, paradigm: str, entity: str, action: int, repetition: int = 0) -> int:
        if not 0 <= action < DOMAIN_SIZE:
            raise ValueError("illegal action")
        if self.kind == "null":
            return self._rng_for(paradigm, entity, action, repetition, "null").randrange(DOMAIN_SIZE)

        y = self.noiseless(paradigm, entity, action)
        rng = self._rng_for(paradigm, entity, action, repetition, "noise")
        if rng.random() < self.noise_rate:
            alternatives = [v for v in range(DOMAIN_SIZE) if v != y]
            return rng.choice(alternatives)
        return y
