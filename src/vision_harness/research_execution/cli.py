"""Inspectable command line entry point for one isolated research-execution trial."""

import argparse
from pathlib import Path

from ..config import load_settings
from .runtime import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["vanilla", "full"], required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/research-execution.toml"))
    parser.add_argument("--development-prefix", type=Path)
    args = parser.parse_args()
    run(args.query, args.mode, load_settings(args.config), args.output, development_prefix=args.development_prefix)


if __name__ == "__main__":
    main()
