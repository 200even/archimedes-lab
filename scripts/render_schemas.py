from __future__ import annotations

import hashlib
import json
from pathlib import Path

from archimedes_v0.ast_schema import ExperimentAST, TheoryAST

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "schemas"
OUT.mkdir(exist_ok=True)

MODELS = {
    "theory_ast.schema.json": TheoryAST,
    "experiment_ast.schema.json": ExperimentAST,
}

manifest = {}
for filename, model in MODELS.items():
    payload = json.dumps(model.model_json_schema(), sort_keys=True, separators=(",", ":")) + "\n"
    path = OUT / filename
    path.write_text(payload, encoding="utf-8")
    manifest[filename] = {
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "bytes": len(payload.encode()),
    }

(OUT / "SCHEMA_MANIFEST.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

for name, meta in manifest.items():
    print(f"{name}: {meta['sha256']} ({meta['bytes']} bytes)")
