from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import venv


def _venv_python(root: Path) -> Path:
    directory = root / ("Scripts" if sys.platform == "win32" else "bin")
    return directory / ("python.exe" if sys.platform == "win32" else "python")


def _venv_command(root: Path) -> Path:
    directory = root / ("Scripts" if sys.platform == "win32" else "bin")
    return directory / ("sheetlens.exe" if sys.platform == "win32" else "sheetlens")


def _sdist_members(path: Path) -> set[str]:
    with tarfile.open(path, "r:gz") as archive:
        names = [member.name for member in archive.getmembers() if member.name]
    roots = {name.split("/", 1)[0] for name in names}
    if len(roots) != 1:
        raise SystemExit(f"sdist must have one root directory, found {sorted(roots)}")
    root = next(iter(roots))
    prefix = f"{root}/"
    return {name.removeprefix(prefix) for name in names if name.startswith(prefix)}


def _check_sdist(path: Path) -> None:
    members = _sdist_members(path)
    required = {
        ".gitignore",
        "PKG-INFO",
        "README.md",
        "pyproject.toml",
        "src/sheetlens/__init__.py",
    }
    missing = sorted(required - members)
    if missing:
        raise SystemExit(f"sdist is missing required members: {missing}")
    unexpected = sorted(
        member
        for member in members
        if member not in {".gitignore", "PKG-INFO", "README.md", "pyproject.toml"}
        and not member.startswith("src/")
    )
    if unexpected:
        raise SystemExit(f"sdist contains unexpected members: {unexpected}")
    if any(member.endswith((".xls", ".xlsx", ".xlsm", ".xlsb", ".xltx", ".xltm")) for member in members):
        raise SystemExit("sdist contains an Excel file")


def main() -> None:
    wheels = sorted(Path("dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one wheel in dist, found {len(wheels)}")
    sdists = sorted(Path("dist").glob("*.tar.gz"))
    if len(sdists) != 1:
        raise SystemExit(f"expected exactly one sdist in dist, found {len(sdists)}")
    _check_sdist(sdists[0])

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
            [
                str(python),
                "-c",
                """
from importlib.metadata import metadata
import sheetlens
from sheetlens.cli import app

data = metadata("sheetlens")
assert sheetlens and app
assert data["Name"] == "sheetlens"
assert data["Author"] == "tonny-lec"
assert data["Description-Content-Type"] == "text/markdown"
assert "Private :: Do Not Upload" in (data.get_all("Classifier") or [])
assert not data.get("License")
assert any(item == "Repository, https://github.com/tonny-lec/sheetlens" for item in data.get_all("Project-URL") or [])
""",
            ],
            check=True,
        )
        subprocess.run([str(_venv_command(environment)), "--help"], check=True)


if __name__ == "__main__":
    main()
