from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def _venv_python(root: Path) -> Path:
    directory = root / ("Scripts" if sys.platform == "win32" else "bin")
    return directory / ("python.exe" if sys.platform == "win32" else "python")


def _venv_command(root: Path) -> Path:
    directory = root / ("Scripts" if sys.platform == "win32" else "bin")
    return directory / ("sheetlens.exe" if sys.platform == "win32" else "sheetlens")


def main() -> None:
    wheels = sorted(Path("dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one wheel in dist, found {len(wheels)}")

    with tempfile.TemporaryDirectory(prefix="sheetlens-wheel-smoke-") as directory:
        environment = Path(directory) / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_python(environment)
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                str(wheels[0].resolve()),
            ],
            check=True,
        )
        subprocess.run(
            [str(python), "-c", "import sheetlens; from sheetlens.cli import app; assert app"],
            check=True,
        )
        subprocess.run([str(_venv_command(environment)), "--help"], check=True)


if __name__ == "__main__":
    main()
