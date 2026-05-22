from page_objects.base_page import BasePage


class OverViewPage(BasePage):
    page_title = '//div[@class="title_page"]'
    transaction_list = "//a[descendant::span[contains(text(), 'Transactions')]]/img"
