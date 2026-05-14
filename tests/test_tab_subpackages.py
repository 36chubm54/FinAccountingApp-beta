from __future__ import annotations

import importlib


def test_settings_reports_and_mandatory_subpackages_are_importable() -> None:
    settings_pkg = importlib.import_module("gui.tabs.settings")
    settings_builder = importlib.import_module("gui.tabs.settings.builder")
    settings_sections = importlib.import_module("gui.tabs.settings.sections")
    mandatory_pkg = importlib.import_module("gui.tabs.mandatory")
    mandatory_builder = importlib.import_module("gui.tabs.mandatory.builder")
    mandatory_section = importlib.import_module("gui.tabs.mandatory.section")
    mandatory_actions = importlib.import_module("gui.tabs.mandatory.actions")
    mandatory_widgets = importlib.import_module("gui.tabs.mandatory.widgets")
    reports_pkg = importlib.import_module("gui.tabs.reports")
    reports_builder = importlib.import_module("gui.tabs.reports.builder")
    reports_controller = importlib.import_module("gui.tabs.reports.controller")
    reports_layout = importlib.import_module("gui.tabs.reports.layout")
    reports_render = importlib.import_module("gui.tabs.reports.render")

    assert settings_pkg.build_settings_tab is settings_builder.build_settings_tab
    assert hasattr(settings_sections, "build_currency_section")
    assert hasattr(settings_sections, "build_backup_section")
    assert hasattr(settings_sections, "build_audit_section")

    assert mandatory_pkg.build_mandatory_tab is mandatory_builder.build_mandatory_tab
    assert hasattr(mandatory_section, "build_mandatory_section")
    assert hasattr(mandatory_actions, "save_add_to_records")
    assert hasattr(mandatory_widgets, "build_add_mandatory_panel")

    assert reports_pkg.build_reports_tab is reports_builder.build_reports_tab
    assert hasattr(reports_builder, "ReportsFrame")
    assert hasattr(reports_controller, "ReportsController")
    assert hasattr(reports_layout, "build_reports_layout")
    assert hasattr(reports_render, "refresh_operations_table")
