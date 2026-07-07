import subprocess
import sys
from pathlib import Path


def test_make_dummy_then_extract(tmp_path):
    out = tmp_path / "見積管理.xlsx"
    subprocess.run(
        [sys.executable, "eval/make_dummy.py", str(out)],
        check=True,
        cwd=Path(__file__).parent.parent,
    )
    assert out.exists()
    from sheetlens.pipeline import extract_workbook

    proj = extract_workbook(out)
    md = (proj / "structure" / "sheet-見積入力.md").read_text(encoding="utf-8")
    assert "VLOOKUP" in md  # 単価の参照数式がパターンとして出る
    assert "通常" in md and "特急" in md  # プルダウン選択肢の展開
