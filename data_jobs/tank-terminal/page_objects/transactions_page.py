from page_objects.base_page import BasePage


class TransactionsPage(BasePage):
    transactie_tabel = "//table[@class='tableau'][not(descendant::td[contains(text(), 'Filtering' )])]//table/parent::td"
