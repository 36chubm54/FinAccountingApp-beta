from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .import_parser import ParsedImportData, parse_import_file
    from .import_service import ImportService

__all__ = ["ImportService", "ParsedImportData", "parse_import_file"]


def __getattr__(name: str):
    if name in {"ParsedImportData", "parse_import_file"}:
        from .import_parser import ParsedImportData, parse_import_file

        exports = {
            "ParsedImportData": ParsedImportData,
            "parse_import_file": parse_import_file,
        }
        return exports[name]
    if name == "ImportService":
        from .import_service import ImportService

        return ImportService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
