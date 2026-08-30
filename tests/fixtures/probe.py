from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("--invalid", action="store_true")
    args = parser.parse_args()
    if args.invalid:
        print("not-json")
        return
    print(args.state.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
