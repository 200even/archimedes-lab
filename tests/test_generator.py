from collections import Counter
from dataclasses import asdict

from archimedes_v0.generator import generate_world
from archimedes_v0.world import HiddenWorldRuntime
from archimedes_v0.constants import (
    DOMAIN_SIZE,
    NUM_ENTITIES,
    BROKER_BUDGET_TOTAL,
    HIDDEN_LATENT_CARDINALITIES,
    MIN_ENTITIES_PER_LATENT_STATE,
)


def test_causal_world_valid_and_reproducible():
    p1, h1, r1 = generate_world(12345)
    p2, h2, r2 = generate_world(12345)
    assert asdict(p1) == asdict(p2)
    assert asdict(h1) == asdict(h2)
    assert r1["accepted"] and r2["accepted"]
    assert len(p1.entities) == NUM_ENTITIES
    assert p1.broker_budget["total"] == BROKER_BUDGET_TOTAL


def test_hidden_cardinality_is_bounded_balanced_and_b_split_is_stratified():
    _, h, r = generate_world(9)
    k = h.latent_cardinality
    q = h.latent_q_by_entity
    counts = Counter(q.values())
    assert k in HIDDEN_LATENT_CARDINALITIES
    assert set(counts) == set(range(k))
    assert min(counts.values()) >= MIN_ENTITIES_PER_LATENT_STATE
    assert max(counts.values()) - min(counts.values()) <= 1
    assert {q[e] for e in h.b_calibration_entities} == set(range(k))
    assert {q[e] for e in h.b_transfer_entities} == set(range(k))
    assert r["b_split_ok"]
    assert r["smt_nonisomorphic_ok"]


def test_observation_replay_is_deterministic():
    _, h, _ = generate_world(88)
    rt = HiddenWorldRuntime(asdict(h))
    a = rt.observe("A", "entity_00", 3, repetition=4)
    b = rt.observe("A", "entity_00", 3, repetition=4)
    assert a == b


def test_null_world_has_no_hidden_causal_program_or_cardinality():
    _, h, r = generate_world(77, null_world=True)
    assert h.latent_cardinality is None
    assert h.latent_q_by_entity is None
    assert h.program_a is None and h.program_b is None
    rt = HiddenWorldRuntime(asdict(h))
    assert 0 <= rt.observe("A", "entity_00", 0, 0) < DOMAIN_SIZE
    assert r["accepted"]


def test_many_seeds_pass_frozen_filters():
    for seed in range(50):
        _, _, report = generate_world(seed)
        assert report["accepted"], (seed, report)
        assert report["smt_nonisomorphic_ok"]


def test_admitted_worlds_cover_all_frozen_templates_and_cardinalities():
    a_templates, b_templates, cardinalities = set(), set(), set()
    for seed in range(100):
        _, h, _ = generate_world(seed)
        a_templates.add(h.program_a["template"])
        b_templates.add(h.program_b["template"])
        cardinalities.add(h.latent_cardinality)
    assert a_templates == {"A1", "A2"}
    assert b_templates == {"B1", "B2"}
    assert cardinalities == set(HIDDEN_LATENT_CARDINALITIES)
