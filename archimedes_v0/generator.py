from __future__ import annotations
import hashlib
import json
import random
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from .constants import (
    SCHEMA_VERSION,
    DOMAIN_SIZE,
    NUM_ENTITIES,
    HIDDEN_LATENT_CARDINALITIES,
    PARADIGM_A_TEMPLATES,
    PARADIGM_B_TEMPLATES,
    ODD_MULTIPLIERS,
    ROTATIONS,
    MEASUREMENT_NOISE_RATE,
    BROKER_BUDGET_TOTAL,
    BUDGET_A_DISCOVERY,
    BUDGET_A_THEORY_EVAL,
    BUDGET_B_CALIBRATION,
    BUDGET_B_THEORY_EVAL,
    BUDGET_B_TRANSFER_EVAL,
)
from .grammar import Program, assert_grammar_invariants
from .validation import validate_hidden_world

@dataclass(frozen=True)
class PublicWorld:
    schema_version: str
    world_id: str
    world_kind: str
    domain_size: int
    entities: list[str]
    legal_action_values: list[int]
    paradigms: list[str]
    measurement: dict[str, Any]
    broker_budget: dict[str, int]
    semantics: dict[str, str]

@dataclass(frozen=True)
class HiddenWorldSpec:
    schema_version: str
    world_id: str
    world_kind: str
    generator_seed: int
    latent_cardinality: int | None
    latent_q_by_entity: dict[str, int] | None
    program_a: dict[str, Any] | None
    program_b: dict[str, Any] | None
    b_calibration_entities: list[str]
    b_transfer_entities: list[str]
    measurement_noise_rate: float
    measurement_noise_key: str


def _rng(seed: int, namespace: str) -> random.Random:
    digest = hashlib.sha256(f"{namespace}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _perm(rng: random.Random) -> list[int]:
    p = list(range(DOMAIN_SIZE))
    rng.shuffle(p)
    return p


def _sample_program_a(rng: random.Random) -> Program:
    template = rng.choice(PARADIGM_A_TEMPLATES)
    if template == "A1":
        params = {"a": rng.choice(ODD_MULTIPLIERS), "c1": rng.randrange(DOMAIN_SIZE), "c2": rng.randrange(DOMAIN_SIZE), "perm": _perm(rng)}
    elif template == "A2":
        params = {"a": rng.choice(ODD_MULTIPLIERS), "c1": rng.randrange(DOMAIN_SIZE), "perm": _perm(rng)}
    else:
        raise AssertionError(template)
    p = Program(template, params)
    assert_grammar_invariants(p)
    return p


def _sample_program_b(rng: random.Random) -> Program:
    template = rng.choice(PARADIGM_B_TEMPLATES)
    if template == "B1":
        params = {"r": rng.choice(ROTATIONS), "s": rng.choice(ROTATIONS), "perm": _perm(rng)}
    elif template == "B2":
        params = {"r": rng.choice(ROTATIONS), "c1": rng.randrange(DOMAIN_SIZE), "c2": rng.randrange(DOMAIN_SIZE), "perm": _perm(rng)}
    else:
        raise AssertionError(template)
    p = Program(template, params)
    assert_grammar_invariants(p)
    return p


def _balanced_q_values(k: int, rng: random.Random) -> list[int]:
    """Create a near-balanced hidden partition without exposing k publicly."""
    base, remainder = divmod(NUM_ENTITIES, k)
    states = list(range(k))
    rng.shuffle(states)
    counts = {q: base + (1 if q in set(states[:remainder]) else 0) for q in range(k)}
    values = [q for q in range(k) for _ in range(counts[q])]
    rng.shuffle(values)
    return values


def _balanced_b_split(entities: list[str], q_by_entity: dict[str, int], k: int, rng: random.Random) -> tuple[list[str], list[str]]:
    """Split 8/8 while placing every hidden state on both sides."""
    groups: dict[int, list[str]] = {}
    for q in range(k):
        members = [e for e in entities if q_by_entity[e] == q]
        rng.shuffle(members)
        groups[q] = members

    odd_states = [q for q, members in groups.items() if len(members) % 2]
    rng.shuffle(odd_states)
    extra_to_cal = set(odd_states[::2])

    cal: list[str] = []
    transfer: list[str] = []
    for q in range(k):
        members = groups[q]
        half = len(members) // 2
        cal.extend(members[:half])
        transfer.extend(members[half:2 * half])
        if len(members) % 2:
            (cal if q in extra_to_cal else transfer).append(members[-1])

    if len(cal) != NUM_ENTITIES // 2 or len(transfer) != NUM_ENTITIES // 2:
        raise AssertionError("balanced split construction failed")
    return sorted(cal), sorted(transfer)


def generate_world(seed: int, *, null_world: bool = False, max_attempts: int = 1000, world_id: str | None = None) -> tuple[PublicWorld, HiddenWorldSpec, dict[str, Any]]:
    entities = [f"entity_{i:02d}" for i in range(NUM_ENTITIES)]
    kind = "null" if null_world else "causal"
    if world_id is None:
        world_id = "v0-dev-" + hashlib.sha256(f"archimedes-v0-public:{seed}".encode()).hexdigest()[:16]

    public = PublicWorld(
        schema_version=SCHEMA_VERSION,
        world_id=world_id,
        world_kind="experimental",
        domain_size=DOMAIN_SIZE,
        entities=entities,
        legal_action_values=list(range(DOMAIN_SIZE)),
        paradigms=["A", "B"],
        measurement={"output_name": "y", "output_domain": list(range(DOMAIN_SIZE)), "known_corruption_rate": MEASUREMENT_NOISE_RATE},
        broker_budget={
            "total": BROKER_BUDGET_TOTAL,
            "A_discovery": BUDGET_A_DISCOVERY,
            "A_theory_eval": BUDGET_A_THEORY_EVAL,
            "B_calibration": BUDGET_B_CALIBRATION,
            "B_theory_eval": BUDGET_B_THEORY_EVAL,
            "B_transfer_eval": BUDGET_B_TRANSFER_EVAL,
        },
        semantics={
            "entity_ids": "opaque persistent identifiers",
            "action_values": "opaque legal intervention values",
            "output": "opaque categorical measurement",
        },
    )

    noise_key = hashlib.sha256(f"measurement:{seed}:archimedes-v0".encode()).hexdigest()
    if null_world:
        split_rng = _rng(seed, "split")
        shuffled = entities.copy(); split_rng.shuffle(shuffled)
        hidden = HiddenWorldSpec(
            schema_version=SCHEMA_VERSION,
            world_id=world_id,
            world_kind=kind,
            generator_seed=seed,
            latent_cardinality=None,
            latent_q_by_entity=None,
            program_a=None,
            program_b=None,
            b_calibration_entities=sorted(shuffled[:NUM_ENTITIES // 2]),
            b_transfer_entities=sorted(shuffled[NUM_ENTITIES // 2:]),
            measurement_noise_rate=MEASUREMENT_NOISE_RATE,
            measurement_noise_key=noise_key,
        )
        report = {"accepted": True, "kind": "null", "reason": "null worlds intentionally contain no causal signal"}
        return public, hidden, report

    for attempt in range(max_attempts):
        rng = _rng(seed + attempt * 1000003, "world")
        k = rng.choice(HIDDEN_LATENT_CARDINALITIES)
        q_values = _balanced_q_values(k, rng)
        q_by_entity = dict(zip(entities, q_values, strict=True))
        pa, pb = _sample_program_a(rng), _sample_program_b(rng)
        cal, transfer = _balanced_b_split(entities, q_by_entity, k, rng)

        hidden = HiddenWorldSpec(
            schema_version=SCHEMA_VERSION,
            world_id=world_id,
            world_kind=kind,
            generator_seed=seed,
            latent_cardinality=k,
            latent_q_by_entity=q_by_entity,
            program_a=pa.to_dict(),
            program_b=pb.to_dict(),
            b_calibration_entities=cal,
            b_transfer_entities=transfer,
            measurement_noise_rate=MEASUREMENT_NOISE_RATE,
            measurement_noise_key=noise_key,
        )
        report = validate_hidden_world(hidden)
        if report["accepted"]:
            report["generation_attempt"] = attempt
            return public, hidden, report
    raise RuntimeError(f"could not generate valid world after {max_attempts} attempts")


def write_world_bundle(out_dir: str | Path, seed: int, *, null_world: bool = False, world_id: str | None = None) -> dict[str, str]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    if world_id is None:
        world_id = f"v0-world-{uuid.uuid4().hex[:16]}"
    public, hidden, report = generate_world(seed, null_world=null_world, world_id=world_id)
    pub_path = out / f"{public.world_id}.public.json"
    hid_path = out / f"{public.world_id}.hidden.json"
    rep_path = out / f"{public.world_id}.validation.json"
    pub_path.write_text(json.dumps(asdict(public), indent=2, sort_keys=True))
    hid_path.write_text(json.dumps(asdict(hidden), indent=2, sort_keys=True))
    rep_path.write_text(json.dumps(report, indent=2, sort_keys=True))
    return {"public": str(pub_path), "hidden": str(hid_path), "validation": str(rep_path)}
