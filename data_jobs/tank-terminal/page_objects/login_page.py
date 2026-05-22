from lib2to3.pytree import Base
from .base_page import BasePage


class LoginPage(BasePage):
    username_input = '//input[@id="Field__UserLogin"]'
    password_input = '//input[@id="Field__UserPassword"]'
    confirm_button = '//td[contains(text(), "Confirm")]'
    continue_button = '//td[contains(text(), "Continue")]'
    language_select = "//select[@id='__Language__' ]"
