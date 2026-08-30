"""Build the deterministic examples archive and checksum manifest."""

from __future__ import annotations

import argparse
import hashlib
import os
import zipfile
from pathlib import Path

from webhookwitness import __version__

ROOT = Path(__file__).parents[1]
FIXED_TIME = (2026, 8, 30, 0, 0, 0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    dist = args.dist.resolve()
    dist.mkdir(parents=True, exist_ok=True)

    tag = os.environ.get("GITHUB_REF_NAME")
    if tag is not None and tag != f"v{__version__}":
        raise SystemExit(f"tag {tag!r} does not match package version v{__version__}")

    distributions = sorted([*dist.glob("*.whl"), *dist.glob("*.tar.gz")])
    if len(distributions) != 2:
        raise SystemExit("expected exactly one wheel and one source distribution")

    archive = dist / f"webhookwitness-{__version__}-examples.zip"
    example_files = sorted(
        path
        for path in (ROOT / "examples").rglob("*")
        if path.is_file() and "runtime" not in path.parts and "__pycache__" not in path.parts
    )
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in example_files:
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(relative, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())

    artifacts = [*distributions, archive]
    manifest = "".join(f"{sha256(path)}  {path.name}\n" for path in artifacts)
    (dist / "SHA256SUMS.txt").write_text(manifest, encoding="utf-8", newline="\n")
    print(f"WEBHOOKWITNESS_RELEASE_ASSETS={len(artifacts) + 1}")


if __name__ == "__main__":
    main()
