"""Overview page selectors for the Tank Terminal web UI."""

from data_jobs.tank_terminal.page_objects.base_page import BasePage


class OverviewPage(BasePage):
    """Selectors for the Tank Terminal overview page."""

    page_title = '//div[@class="title_page"]'
    transaction_links = [
        "//a[descendant::span[contains(normalize-space(), 'Transactions')]]",
        "//a[contains(normalize-space(), 'Transactions')]",
        "//span[contains(normalize-space(), 'Transactions')]",
    ]
