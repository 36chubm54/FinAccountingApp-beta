from __future__ import annotations

KIND_TO_FOREGROUND: dict[str, str] = {
    "income": "#166534",
    "expense": "#b91c1c",
    "mandatory": "#b6ad13",
    "transfer": "#1d4ed8",
}


def foreground_for_kind(kind: str) -> str | None:
    return KIND_TO_FOREGROUND.get((kind or "").strip().lower() or "")
