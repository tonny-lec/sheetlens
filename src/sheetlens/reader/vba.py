from pathlib import Path

from oletools.olevba import VBA_Parser

from sheetlens.model import ir

_MACRO_SUFFIXES = (".xlsm", ".xltm")


def extract_vba(path: Path) -> list[ir.VbaModule]:
    if path.suffix.lower() not in _MACRO_SUFFIXES:
        return []
    parser = VBA_Parser(str(path))
    try:
        if not parser.detect_vba_macros():
            return []
        return [
            ir.VbaModule(name=Path(vba_filename).name, code=vba_code)
            for (_f, _s, vba_filename, vba_code) in parser.extract_macros()
        ]
    finally:
        parser.close()
