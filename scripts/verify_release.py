"""Run the local equivalent of every v0.1.0 release gate."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).parents[1]
TMP = ROOT / ".tmp"


def run(command: list[str], expected: int = 0) -> None:
    print(f"+ {subprocess.list2cmdline(command)}", flush=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != expected:
        raise SystemExit(
            f"expected exit {expected}, received {completed.returncode}: "
            f"{subprocess.list2cmdline(command)}"
        )


def installed_cli(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "webhookwitness.exe"
    return environment / "bin" / "webhookwitness"


def main() -> None:
    TMP.mkdir(exist_ok=True)
    run([sys.executable, "-m", "ruff", "check", "."])
    run([sys.executable, "-m", "ruff", "format", "--check", "."])
    run([sys.executable, "-m", "mypy", "src", "tests", "scripts"])
    run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--basetemp=.tmp/pytest-release",
            "--cov=webhookwitness",
            "--cov-branch",
            "--cov-report=term-missing",
            "--cov-report=xml",
        ]
    )
    run([sys.executable, "scripts/run_demo.py"])

    with tempfile.TemporaryDirectory(prefix="release-", dir=TMP) as directory:
        scratch = Path(directory)
        dist = scratch / "dist"
        run(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--outdir",
                str(dist),
                str(ROOT),
            ]
        )
        wheel = next(dist.glob("*.whl"))
        environment = scratch / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run([str(python), "-m", "pip", "install", "--no-deps", str(wheel)])

        cli = str(installed_cli(environment))
        run([cli, "version"])
        run([cli, "validate", "examples/passing.json"])
        run([cli, "run", "examples/passing.json", "--artifacts", str(scratch / "pass")])
        run(
            [cli, "run", "examples/failing.json", "--artifacts", str(scratch / "fail")],
            expected=1,
        )

    run(["git", "diff", "--check"])
    run(["git", "diff", "--exit-code"])
    run(["git", "diff", "--cached", "--exit-code"])
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if untracked.returncode != 0 or untracked.stdout:
        raise SystemExit(f"release gate requires a clean tree; untracked:\n{untracked.stdout}")

    secret_scan = subprocess.run(
        [
            "git",
            "grep",
            "-I",
            "-n",
            "-E",
            "BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|ghp_[A-Za-z0-9]{30,}|github_pat_",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if secret_scan.returncode == 0:
        raise SystemExit(f"credential-like tracked content found:\n{secret_scan.stdout}")
    if secret_scan.returncode != 1:
        raise SystemExit(secret_scan.stderr)

    print("WEBHOOKWITNESS_RELEASE_GATE=PASS")


if __name__ == "__main__":
    main()
