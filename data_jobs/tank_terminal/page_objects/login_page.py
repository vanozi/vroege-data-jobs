"""Login page selectors for the Tank Terminal web UI."""

from data_jobs.tank_terminal.page_objects.base_page import BasePage


class LoginPage(BasePage):
    """Selectors for the Tank Terminal login page."""

    username_input = '//input[@id="Field__UserLogin"]'
    password_input = '//input[@id="Field__UserPassword"]'
    confirm_button = '//td[contains(text(), "Confirm")]'
    continue_button = '//td[contains(text(), "Continue")]'
    language_select = "//select[@id='__Language__']"
