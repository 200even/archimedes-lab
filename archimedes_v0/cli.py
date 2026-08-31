from __future__ import annotations
import argparse
from .generator import write_world_bundle

def main():
    ap = argparse.ArgumentParser(description="Generate a frozen Archimedes V0 hidden-world bundle")
    ap.add_argument("seed", type=int)
    ap.add_argument("--out", default="worlds")
    ap.add_argument("--null", action="store_true", dest="null_world")
    args = ap.parse_args()
    paths = write_world_bundle(args.out, args.seed, null_world=args.null_world)
    for k, v in paths.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()
