from __future__ import annotations

KIND_TO_FOREGROUND: dict[str, str] = {
    "income": "#378977",
    "expense": "#b93748",
    "mandatory": "#c5a742",
    "transfer": "#2f6fed",
}


def foreground_for_kind(kind: str) -> str | None:
    return KIND_TO_FOREGROUND.get((kind or "").strip().lower() or "")
