from __future__ import annotations

from archimedes_v0.v1_v11_benchmark_runner import derive_world_seed, opaque_world_id


def test_frozen_seed_schedule_is_deterministic_and_phase_separated():
    null = [derive_world_seed("vanguard", i) for i in range(100)]
    causal = [derive_world_seed("paired", i) for i in range(100)]
    assert len(set(null)) == 100
    assert len(set(causal)) == 100
    assert set(null).isdisjoint(causal)
    assert null == [derive_world_seed("vanguard", i) for i in range(100)]
    assert causal == [derive_world_seed("paired", i) for i in range(100)]


def test_opaque_ids_do_not_encode_condition_or_seed():
    ids = [opaque_world_id("vanguard", i) for i in range(100)] + [opaque_world_id("paired", i) for i in range(100)]
    assert len(set(ids)) == 200
    assert all(x.startswith("v11-w-") for x in ids)
    assert all("null" not in x and "causal" not in x and "vanguard" not in x and "paired" not in x for x in ids)


def test_world_schedule_bounds_are_hard():
    for phase in ("vanguard", "paired"):
        for bad in (-1, 100, 1000):
            try:
                derive_world_seed(phase, bad)
            except ValueError:
                pass
            else:
                raise AssertionError("out-of-range benchmark index accepted")
