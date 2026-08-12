"""Transactions export page selectors for the Tank Terminal web UI."""

from data_jobs.tank_terminal.page_objects.base_page import BasePage


class ExportTransactionsPage(BasePage):
    """Selectors for the ProFleet transactions export screen."""

    export_transactions_page_title = "//div[contains(@class, 'noprint') and normalize-space(.)=\"Export 'Transactions'\"]"
    template_select = "//select[@id='Field__ReportSelect']"
    template_option_value = "525"
    start_date_input = [
        "//input[@id='Field__filter__EX_Transac_StartDateTime']",
    ]
    end_date_input = [
        "//input[@id='Field__filter__EX_Transac_end__StartDateTime']",
    ]
    export_button = [
        "(//td[contains(@onclick, 'Action=OneShotDoExport') and normalize-space(.)='Export'])[2]",
    ]
