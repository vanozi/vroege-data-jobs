import json
import os
import time
import unicodedata

import lxml.html as lh
import pandas as pd
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from page_objects.login_page import LoginPage
from page_objects.overview_page import OverViewPage
from page_objects.transactions_page import TransactionsPage

load_dotenv()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://82.197.193.195:8080/cgi-bin/index.php")
    # Taal selecteren
    page.locator(LoginPage.language_select).select_option("English")
    # Inloggen
    page.locator(LoginPage.username_input).fill(os.getenv("USERNAME"))
    page.locator(LoginPage.password_input).fill(os.getenv("PASSWORD"))
    page.locator(LoginPage.confirm_button).click()
    time.sleep(3)
    if page.locator(LoginPage.continue_button).is_visible():
        page.locator(LoginPage.continue_button).click()
        # Naar transactie lijst
        time.sleep(3)

    page.locator(OverViewPage.transaction_list).click()
    time.sleep(3)

    # html transactie tabel verkrijgen
    transactie_tabel = page.inner_html(TransactionsPage.transactie_tabel)
    transactie_tabel = unicodedata.normalize("NFKD", transactie_tabel)

    browser.close()

# Html tabel verwerken/parsen
tree = lh.fragment_fromstring(transactie_tabel)

columns = [
    "vehicle",
    "driver",
    "transaction_type",
    "acquisition_mode",
    "transaction_status",
    "start_date_time",
    "transaction_number",
    "product",
    "quantity",
    "transaction_duration",
    "meter",
]
# tree.xpath("//tbody/tr[1]/td[string-length(text()) > 1]/text()")

data = []
for x in range(3, 28):
    row_data = []
    for i in range(3, 14):
        td_string = tree.xpath(f"//tbody/tr[{x}]/td[{i}]/text()")[0]
        td_string = td_string.replace("\xa0", " ")
        row_data.append(td_string)
    data.append(row_data)

# pandas dataframe maken
df = pd.DataFrame(data, columns=columns)
df_dict = df.to_dict(orient="records")

for transactie in df_dict:
    transactie["quantity"] = transactie["quantity"][:-2]
    if transactie["meter"] != "":
        if transactie["meter"].endswith("h"):
            transactie["meter_type"] = "h"
            transactie["meter"] = transactie["meter"][:-2]
        elif transactie["meter"].endswith("km"):
            transactie["meter_type"] = "km"
            transactie["meter"] = transactie["meter"][:-3]
        else:
            transactie["meter"] = None
            transactie["meter_type"] = None
    res = requests.post(
        url=os.getenv("BASE_URL_API") + "/tank_transactions/",
        data=json.dumps(transactie),
    )
