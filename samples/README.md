# Sample-world policy

No condition-labeled or seed-labeled public world files are checked into this repository.

The early development samples encoded `causal` / `null` and raw seeds in filenames; V0.1.1 classified that as a metadata-leakage route. Generate temporary benchmark bundles with `write_world_bundle()` instead. Those bundles use opaque random public IDs while keeping true condition, seed, hidden cardinality, programs, and validation reports on the trusted side.

Generated `*.hidden.json` and `*.validation.json` files must never be mounted into an agent environment and are excluded by `.gitignore`.
