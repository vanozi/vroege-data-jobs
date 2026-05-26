"""Transactions page selectors for the Tank Terminal web UI."""

from data_jobs.tank_terminal.page_objects.base_page import BasePage


class TransactionsPage(BasePage):
    """Selectors for the Tank Terminal transactions page."""

    transaction_tables = (
        "//table[@class='tableau'][not(descendant::td[contains(text(), 'Filtering')])]"
    )
