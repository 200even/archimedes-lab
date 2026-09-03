from __future__ import annotations

import hashlib
import json
from pathlib import Path

from archimedes_v0.v1_protocol import (
    ENTITIES,
    PartitionHypothesis,
    build_b_calibration_schedule,
    build_b_transfer_schedule,
    canonical_digest,
    canonicalize_partition,
)


def partition_from_groups(groups: list[list[str]], hypothesis_id: str):
    mapping = {}
    for label, members in enumerate(groups):
        for entity in members:
            mapping[entity] = label
    return PartitionHypothesis(hypothesis_id=hypothesis_id, group_count=len(groups), entity_group=mapping)


def fixture_manifest():
    fixtures = {
        "balanced_k2": [list(ENTITIES[:8]), list(ENTITIES[8:])],
        "unbalanced_k3": [list(ENTITIES[:3]), list(ENTITIES[3:8]), list(ENTITIES[8:])],
        "balanced_k4": [list(ENTITIES[0:4]), list(ENTITIES[4:8]), list(ENTITIES[8:12]), list(ENTITIES[12:16])],
        "metamorphic_k4": [
            ["entity_00", "entity_05", "entity_10", "entity_15"],
            ["entity_01", "entity_04", "entity_11", "entity_14"],
            ["entity_02", "entity_07", "entity_08", "entity_13"],
            ["entity_03", "entity_06", "entity_09", "entity_12"],
        ],
    }
    output = {}
    for name in sorted(fixtures):
        partition = canonicalize_partition(partition_from_groups(fixtures[name], f"H-{name}"))
        calibration = build_b_calibration_schedule(partition)
        transfer = build_b_transfer_schedule(partition, calibration)
        output[name] = {
            "partition_digest": partition.digest(),
            "calibration_digest": canonical_digest(calibration),
            "transfer_digest": canonical_digest(transfer),
        }
    payload = json.dumps(output, sort_keys=True, separators=(",", ":"))
    return {
        "fixtures": output,
        "combined_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }


def main():
    manifest = fixture_manifest()
    print(json.dumps(manifest, sort_keys=True, indent=2))

    expected_path = Path("V1_SCHEDULE_DIGEST_MANIFEST.json")
    if expected_path.exists():
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        if manifest != expected:
            raise SystemExit("V1 deterministic schedule digest differs from committed manifest")


if __name__ == "__main__":
    main()
