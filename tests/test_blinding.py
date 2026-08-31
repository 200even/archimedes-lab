import json
from pathlib import Path

from archimedes_v0.generator import generate_world, write_world_bundle


def test_public_metadata_is_condition_blinded():
    causal_public, causal_hidden, _ = generate_world(123, null_world=False)
    null_public, null_hidden, _ = generate_world(123, null_world=True)

    assert causal_public.world_kind == "experimental"
    assert null_public.world_kind == "experimental"
    assert "causal" not in causal_public.world_id
    assert "null" not in null_public.world_id
    assert "00000123" not in causal_public.world_id
    assert "00000123" not in null_public.world_id
    assert causal_hidden.world_kind == "causal"
    assert null_hidden.world_kind == "null"
    assert causal_hidden.generator_seed == 123
    assert null_hidden.generator_seed == 123


def test_written_bundle_uses_opaque_public_filename(tmp_path: Path):
    paths = write_world_bundle(tmp_path, 7, null_world=True)
    public_path = Path(paths["public"])
    public = json.loads(public_path.read_text())
    assert public["world_kind"] == "experimental"
    assert "null" not in public_path.name
    assert "causal" not in public_path.name
    assert "00000007" not in public_path.name
