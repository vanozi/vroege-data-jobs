"""Overview page selectors for the Tank Terminal web UI."""

from data_jobs.tank_terminal.page_objects.base_page import BasePage


class OverviewPage(BasePage):
    """Selectors for the Tank Terminal overview page."""

    page_title = '//div[@class="title_page"]'
    transaction_list = "//a[descendant::span[contains(text(), 'Transactions')]]/img"
