from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImportResult:
    imported: int
    skipped: int
    errors: tuple[str, ...] = field(default_factory=tuple)
    dry_run: bool = False

    def __post_init__(self) -> None:
        # dataclass(frozen=True) + list field would be a "frozen-but-mutable" footgun.
        # Normalize to an immutable tuple even if callers pass a list.
        errors = self.errors
        if not isinstance(errors, tuple):
            object.__setattr__(self, "errors", tuple(errors))

    def summary(self) -> str:
        prefix = "[DRY-RUN] " if self.dry_run else ""
        return (
            f"{prefix}Imported: {self.imported}, "
            f"Skipped: {self.skipped}, "
            f"Errors: {len(self.errors)}"
        )
