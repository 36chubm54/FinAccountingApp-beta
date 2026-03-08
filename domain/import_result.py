from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImportResult:
    imported: int
    skipped: int
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    def summary(self) -> str:
        prefix = "[DRY-RUN] " if self.dry_run else ""
        return (
            f"{prefix}Imported: {self.imported}, "
            f"Skipped: {self.skipped}, "
            f"Errors: {len(self.errors)}"
        )
