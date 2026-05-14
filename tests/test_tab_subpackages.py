from __future__ import annotations

import importlib


def test_settings_reports_and_mandatory_subpackages_are_importable() -> None:
    analytics_shim = importlib.import_module("gui.tabs.analytics_tab")
    analytics_pkg = importlib.import_module("gui.tabs.analytics")
    analytics_builder = importlib.import_module("gui.tabs.analytics.builder")
    analytics_refresh = importlib.import_module("gui.tabs.analytics.refresh")
    analytics_render = importlib.import_module("gui.tabs.analytics.render")
    analytics_summary = importlib.import_module("gui.tabs.analytics.summary_section")
    analytics_breakdown = importlib.import_module("gui.tabs.analytics.breakdown_section")
    analytics_monthly = importlib.import_module("gui.tabs.analytics.monthly_section")
    budget_shim = importlib.import_module("gui.tabs.budget_tab")
    budget_pkg = importlib.import_module("gui.tabs.budget")
    budget_builder = importlib.import_module("gui.tabs.budget.builder")
    budget_actions = importlib.import_module("gui.tabs.budget.actions")
    budget_list = importlib.import_module("gui.tabs.budget.list_section")
    debts_shim = importlib.import_module("gui.tabs.debts_tab")
    debts_pkg = importlib.import_module("gui.tabs.debts")
    debts_builder = importlib.import_module("gui.tabs.debts.builder")
    debts_forms = importlib.import_module("gui.tabs.debts.forms")
    debts_render = importlib.import_module("gui.tabs.debts.render")
    debts_actions = importlib.import_module("gui.tabs.debts.actions")
    debts_keyboard = importlib.import_module("gui.tabs.debts.keyboard")
    debts_history = importlib.import_module("gui.tabs.debts.history_section")
    distribution_shim = importlib.import_module("gui.tabs.distribution_tab")
    distribution_pkg = importlib.import_module("gui.tabs.distribution")
    distribution_builder = importlib.import_module("gui.tabs.distribution.builder")
    distribution_formatting = importlib.import_module("gui.tabs.distribution.formatting")
    distribution_prompts = importlib.import_module("gui.tabs.distribution.prompts")
    distribution_results_data = importlib.import_module("gui.tabs.distribution.results_data")
    distribution_structure = importlib.import_module("gui.tabs.distribution.structure_section")
    distribution_results = importlib.import_module("gui.tabs.distribution.results_section")
    distribution_actions = importlib.import_module("gui.tabs.distribution.actions")
    settings_pkg = importlib.import_module("gui.tabs.settings")
    settings_builder = importlib.import_module("gui.tabs.settings.builder")
    settings_wallets = importlib.import_module("gui.tabs.settings.wallets_section")
    settings_currency = importlib.import_module("gui.tabs.settings.currency_section")
    settings_backup = importlib.import_module("gui.tabs.settings.backup_section")
    mandatory_pkg = importlib.import_module("gui.tabs.mandatory")
    mandatory_builder = importlib.import_module("gui.tabs.mandatory.builder")
    mandatory_section = importlib.import_module("gui.tabs.mandatory.section")
    mandatory_actions = importlib.import_module("gui.tabs.mandatory.actions")
    mandatory_forms = importlib.import_module("gui.tabs.mandatory.forms")
    mandatory_tree = importlib.import_module("gui.tabs.mandatory.tree_section")
    mandatory_keyboard = importlib.import_module("gui.tabs.mandatory.keyboard")
    reports_pkg = importlib.import_module("gui.tabs.reports")
    reports_builder = importlib.import_module("gui.tabs.reports.builder")
    reports_controller = importlib.import_module("gui.tabs.reports.controller")
    reports_layout = importlib.import_module("gui.tabs.reports.layout")
    reports_render = importlib.import_module("gui.tabs.reports.render")
    infographics_shim = importlib.import_module("gui.tabs.infographics_tab")
    infographics_pkg = importlib.import_module("gui.tabs.infographics")
    infographics_builder = importlib.import_module("gui.tabs.infographics.builder")
    infographics_contracts = importlib.import_module("gui.tabs.infographics.contracts")
    infographics_pie = importlib.import_module("gui.tabs.infographics.pie_section")
    infographics_bar = importlib.import_module("gui.tabs.infographics.bar_section")
    infographics_refresh = importlib.import_module("gui.tabs.infographics.refresh")

    assert analytics_shim.build_analytics_tab is analytics_builder.build_analytics_tab
    assert analytics_shim.AnalyticsTabBindings is analytics_pkg.AnalyticsTabBindings
    assert analytics_shim.AnalyticsTabContext is analytics_pkg.AnalyticsTabContext
    assert analytics_shim._draw_breakdown_pie is analytics_render._draw_breakdown_pie
    assert analytics_shim._draw_net_worth_line is analytics_render._draw_net_worth_line
    assert analytics_pkg.build_analytics_tab is analytics_builder.build_analytics_tab
    assert hasattr(analytics_render, "_draw_breakdown_pie")
    assert hasattr(analytics_render, "_draw_net_worth_line")
    assert hasattr(analytics_refresh, "refresh_analytics")
    assert hasattr(analytics_summary, "build_summary_section")
    assert hasattr(analytics_breakdown, "build_breakdown_section")
    assert hasattr(analytics_monthly, "build_monthly_section")

    assert budget_shim.build_budget_tab is budget_builder.build_budget_tab
    assert budget_shim.BudgetTabBindings is budget_pkg.BudgetTabBindings
    assert budget_shim.BudgetTabContext is budget_pkg.BudgetTabContext
    assert budget_shim._normalize_budget_limit_input is budget_actions._normalize_budget_limit_input
    assert budget_shim._visual_budget_state is budget_actions._visual_budget_state
    assert hasattr(budget_list, "_draw_progress_bars")

    assert debts_shim.build_debts_tab is not None
    assert debts_shim.DebtsTabBindings is debts_pkg.DebtsTabBindings
    assert debts_shim.DebtsTabContext is debts_pkg.DebtsTabContext
    assert debts_shim.refresh_debts_views is debts_pkg.refresh_debts_views
    assert debts_shim._segment_widths is debts_render._segment_widths
    assert debts_shim._draw_debt_progress is debts_render._draw_debt_progress
    assert hasattr(debts_shim, "messagebox")
    assert debts_pkg.build_debts_tab is debts_builder.build_debts_tab
    assert hasattr(debts_render, "_segment_widths")
    assert hasattr(debts_render, "_draw_debt_progress")
    assert hasattr(debts_actions, "create_debt_action")
    assert hasattr(debts_forms, "build_create_form")
    assert hasattr(debts_keyboard, "bind_control_shortcuts")
    assert hasattr(debts_history, "refresh_history")

    assert distribution_shim.build_distribution_tab is distribution_builder.build_distribution_tab
    assert distribution_shim.DistributionTabBindings is distribution_pkg.DistributionTabBindings
    assert distribution_shim.DistributionTabContext is distribution_pkg.DistributionTabContext
    assert (
        distribution_shim._snapshot_values_to_display
        is distribution_formatting._snapshot_values_to_display
    )
    assert (
        distribution_shim._parse_snapshot_amount is distribution_formatting._parse_snapshot_amount
    )
    assert distribution_shim._fmt_amount is distribution_formatting._fmt_amount
    assert distribution_shim._default_start is distribution_formatting._default_start
    assert distribution_shim._default_end is distribution_formatting._default_end
    assert distribution_pkg.build_distribution_tab is distribution_builder.build_distribution_tab
    assert hasattr(distribution_formatting, "_snapshot_values_to_display")
    assert hasattr(distribution_prompts, "DistributionActionUi")
    assert hasattr(distribution_results_data, "compose_column_meta")
    assert hasattr(distribution_structure, "build_structure_section")
    assert hasattr(distribution_results, "refresh_results")
    assert hasattr(distribution_actions, "toggle_fixed_row")

    assert settings_pkg.build_settings_tab is settings_builder.build_settings_tab
    assert hasattr(settings_wallets, "build_wallets_section")
    assert hasattr(settings_currency, "build_currency_section")
    assert hasattr(settings_currency, "build_audit_section")
    assert hasattr(settings_backup, "build_backup_section")

    assert mandatory_pkg.build_mandatory_tab is mandatory_builder.build_mandatory_tab
    assert hasattr(mandatory_section, "build_mandatory_section")
    assert hasattr(mandatory_actions, "save_add_to_records")
    assert hasattr(mandatory_forms, "build_add_mandatory_panel")
    assert hasattr(mandatory_tree, "build_mandatory_tree")
    assert hasattr(mandatory_keyboard, "bind_focus_navigation")

    assert reports_pkg.build_reports_tab is reports_builder.build_reports_tab
    assert hasattr(reports_builder, "ReportsFrame")
    assert hasattr(reports_controller, "ReportsController")
    assert hasattr(reports_layout, "build_reports_layout")
    assert hasattr(reports_render, "refresh_operations_table")

    assert infographics_shim.build_infographics_tab is infographics_builder.build_infographics_tab
    assert (
        infographics_shim.InfographicsTabBindings is infographics_contracts.InfographicsTabBindings
    )
    assert infographics_pkg.build_infographics_tab is infographics_builder.build_infographics_tab
    assert infographics_shim.draw_expense_pie is infographics_pie.draw_expense_pie
    assert infographics_shim.update_pie_month_options is infographics_pie.update_pie_month_options
    assert (
        infographics_shim._legend_category_max_width is infographics_pie._legend_category_max_width
    )
    assert hasattr(infographics_bar, "draw_bar_chart")
    assert hasattr(infographics_refresh, "refresh_infographics_charts")
