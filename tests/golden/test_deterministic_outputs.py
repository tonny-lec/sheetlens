from pathlib import Path

from sheetlens.pipeline import extract_workbook


FIXTURE = Path(__file__).parents[1] / "fixtures" / "xlsm" / "openpyxl-vba-test.xlsm"
EXPECTED = Path(__file__).parent / "expected"
GOLDEN_PATHS = (
    Path("manifest.json"),
    Path("questions.md"),
    Path("README.md"),
    Path("structure/raw.json"),
    Path("structure/sheet-Scratch.md"),
)


def _snapshot(project: Path) -> dict[Path, bytes]:
    return {
        relative: (project / relative).read_bytes().replace(b"\r\n", b"\n")
        for relative in GOLDEN_PATHS
    }


def test_representative_fixture_matches_golden(tmp_path: Path):
    project = tmp_path / "openpyxl-vba-test.sheetlens"
    extract_workbook(FIXTURE, project)

    assert _snapshot(project) == _snapshot(EXPECTED)


def test_representative_fixture_reextract_is_byte_identical(tmp_path: Path):
    project = tmp_path / "openpyxl-vba-test.sheetlens"
    extract_workbook(FIXTURE, project)
    first = _snapshot(project)

    extract_workbook(FIXTURE, project)

    assert _snapshot(project) == first
