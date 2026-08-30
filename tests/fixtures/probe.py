from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("--invalid", action="store_true")
    parser.add_argument("--exit-code", type=int, default=0)
    args = parser.parse_args()
    if args.invalid:
        print("not-json")
        return
    print(args.state.read_text(encoding="utf-8"))
    sys.exit(args.exit_code)


if __name__ == "__main__":
    main()
