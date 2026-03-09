from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuditSeverity(Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class AuditFinding:
    """Single finding from one audit check."""

    check: str
    severity: AuditSeverity
    message: str
    detail: str = ""


@dataclass(frozen=True)
class AuditReport:
    """Full result of a data audit run."""

    findings: tuple[AuditFinding, ...]
    db_path: str

    @property
    def errors(self) -> tuple[AuditFinding, ...]:
        return tuple(
            finding for finding in self.findings if finding.severity == AuditSeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[AuditFinding, ...]:
        return tuple(
            finding for finding in self.findings if finding.severity == AuditSeverity.WARNING
        )

    @property
    def passed(self) -> tuple[AuditFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == AuditSeverity.OK)

    @property
    def is_clean(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        return (
            f"Audit complete — "
            f"{len(self.errors)} error(s), "
            f"{len(self.warnings)} warning(s), "
            f"{len(self.passed)} check(s) passed."
        )
