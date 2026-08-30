"""Print the example handler's observable business state as one JSON value."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(state, sort_keys=True))


if __name__ == "__main__":
    main()
