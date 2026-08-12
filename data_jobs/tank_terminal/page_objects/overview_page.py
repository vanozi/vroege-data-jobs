"""Overview page selectors for the Tank Terminal web UI."""

from data_jobs.tank_terminal.page_objects.base_page import BasePage


class OverviewPage(BasePage):
    """Selectors for the Tank Terminal overview page."""

    page_title = '//div[@class="title_page"]'
    administration_link = [
        "//td[contains(@class, 'table_dd') and contains(., 'Administration')]"
    ]
    reports_exports_link = [
        '//*[@id="nav"]/li[1]/ul/li[3]/table/tbody/tr/td',
    ]
    export_link = ['//*[@id="nav"]/li[1]/ul/li[3]/ul/li[3]/table/tbody/tr/td']
    transactions_link = [
        '//*[@id="nav"]/li[1]/ul/li[3]/ul/li[3]/ul/li[1]/table/tbody/tr/td',
    ]
