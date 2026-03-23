from __future__ import annotations

import os
import tkinter as tk
from tkinter import scrolledtext, ttk

from domain.audit import AuditFinding, AuditReport


def safe_destroy(widget) -> None:
    if widget is None:
        return
    try:
        widget.destroy()
    except tk.TclError:
        return


def _format_audit_finding(finding: AuditFinding, *, passed: bool = False) -> str:
    suffix = f" — {finding.detail}" if finding.detail else ""
    prefix = "✔ " if passed else ""
    return f"{prefix}[{finding.check}] {finding.message}{suffix}"


def _populate_audit_section(
    widget: scrolledtext.ScrolledText,
    findings: tuple[AuditFinding, ...],
    *,
    passed: bool = False,
    background: str | None = None,
) -> None:
    if background is not None:
        widget.configure(background=background)
    widget.configure(state="normal")
    widget.delete("1.0", tk.END)
    if findings:
        lines = [_format_audit_finding(finding, passed=passed) for finding in findings]
        widget.insert("1.0", "\n".join(lines))
    else:
        widget.insert("1.0", "(none)")
    widget.configure(state="disabled")


def show_audit_report_dialog(report: AuditReport, parent: tk.Misc) -> None:
    dialog = tk.Toplevel(parent)
    dialog.title("Data Audit Report")
    dialog.minsize(560, 480)
    dialog.transient(parent.winfo_toplevel())

    frame = ttk.Frame(dialog, padding=12)
    frame.pack(fill="both", expand=True)
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_rowconfigure(3, weight=1)
    frame.grid_rowconfigure(4, weight=1)
    frame.grid_rowconfigure(5, weight=1)

    ttk.Label(frame, text=f"Database: {os.path.basename(report.db_path)}").grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(frame, text=report.summary()).grid(row=1, column=0, sticky="w", pady=(4, 10))

    errors_frame = ttk.LabelFrame(frame, text=f"Errors ({len(report.errors)})")
    errors_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
    errors_frame.grid_columnconfigure(0, weight=1)
    errors_frame.grid_rowconfigure(0, weight=1)

    warnings_frame = ttk.LabelFrame(frame, text=f"Warnings ({len(report.warnings)})")
    warnings_frame.grid(row=4, column=0, sticky="nsew", pady=(0, 8))
    warnings_frame.grid_columnconfigure(0, weight=1)
    warnings_frame.grid_rowconfigure(0, weight=1)

    passed_frame = ttk.LabelFrame(frame, text=f"Passed ({len(report.passed)})")
    passed_frame.grid(row=5, column=0, sticky="nsew", pady=(0, 10))
    passed_frame.grid_columnconfigure(0, weight=1)
    passed_frame.grid_rowconfigure(0, weight=1)

    errors_text = scrolledtext.ScrolledText(errors_frame, height=7, wrap="word")
    errors_text.grid(row=0, column=0, sticky="nsew")
    warnings_text = scrolledtext.ScrolledText(warnings_frame, height=7, wrap="word")
    warnings_text.grid(row=0, column=0, sticky="nsew")
    passed_text = scrolledtext.ScrolledText(passed_frame, height=8, wrap="word")
    passed_text.grid(row=0, column=0, sticky="nsew")

    _populate_audit_section(
        errors_text,
        report.errors,
        background="#ffe6e6" if report.errors else None,
    )
    _populate_audit_section(
        warnings_text,
        report.warnings,
        background="#fff9e6" if report.warnings else None,
    )
    _populate_audit_section(
        passed_text,
        report.passed,
        passed=True,
        background="#e6f9e6" if report.is_clean else None,
    )

    close_button = ttk.Button(frame, text="Close", command=dialog.destroy)
    close_button.grid(row=6, column=0, sticky="e")

    dialog.update_idletasks()
    root = parent.winfo_toplevel()
    root_x = root.winfo_rootx()
    root_y = root.winfo_rooty()
    root_w = root.winfo_width()
    root_h = root.winfo_height()
    dialog_w = max(dialog.winfo_width(), 560)
    dialog_h = max(dialog.winfo_height(), 480)
    pos_x = root_x + max((root_w - dialog_w) // 2, 0)
    pos_y = root_y + max((root_h - dialog_h) // 2, 0)
    dialog.geometry(f"{dialog_w}x{dialog_h}+{pos_x}+{pos_y}")
    dialog.grab_set()
    close_button.focus_set()
