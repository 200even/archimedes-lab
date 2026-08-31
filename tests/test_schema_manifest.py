import hashlib
import json
from pathlib import Path

from archimedes_v0.ast_schema import ExperimentAST, TheoryAST


def test_frozen_schema_hashes_match_canonical_models():
    manifest = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "SCHEMA_MANIFEST.json").read_text())
    models = {
        "theory_ast.schema.json": TheoryAST,
        "experiment_ast.schema.json": ExperimentAST,
    }
    for filename, model in models.items():
        payload = json.dumps(model.model_json_schema(), sort_keys=True, separators=(",", ":")) + "\n"
        encoded = payload.encode()
        assert hashlib.sha256(encoded).hexdigest() == manifest[filename]["sha256"]
        assert len(encoded) == manifest[filename]["bytes"]
