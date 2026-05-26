from datetime import datetime

from data_jobs.tank_terminal import parsers


TABLE_HTML = """
<table>
  <tbody>
    <tr>
      <td></td>
      <td>Vehicle</td>
      <td>Driver</td>
      <td>Transaction type</td>
      <td>Acquisition mode</td>
      <td>Transaction status</td>
      <td>Start date-time</td>
      <td>Transaction number</td>
      <td>Product</td>
      <td>Quantity</td>
      <td>Transaction duration</td>
      <td>Meter</td>
      <td></td>
    </tr>
    <tr>
      <td></td>
      <td>Siloking 2022</td>
      <td>Jeffrey</td>
      <td>Dispensing</td>
      <td>Normal</td>
      <td>Normal</td>
      <td>23/08/2022&nbsp;10:30:38</td>
      <td>001012235085</td>
      <td>Diesel</td>
      <td>87.47&nbsp;L</td>
      <td>00:01:07</td>
      <td>271&nbsp;h</td>
      <td></td>
    </tr>
    <tr>
      <td></td>
      <td>09-BSB-9</td>
      <td>geert</td>
      <td>Dispensing</td>
      <td>Normal</td>
      <td>Normal</td>
      <td>22/08/2022&nbsp;17:03:19</td>
      <td>001012234081</td>
      <td>Diesel</td>
      <td>246.40&nbsp;L</td>
      <td>00:04:29</td>
      <td>370187&nbsp;km</td>
      <td></td>
    </tr>
    <tr>
      <td></td>
      <td>Klein materiaal</td>
      <td>Luuk</td>
      <td>Dispensing</td>
      <td>Normal</td>
      <td>Normal</td>
      <td>22/08/2022&nbsp;14:55:45</td>
      <td>001012234080</td>
      <td>Diesel</td>
      <td>56.80&nbsp;L</td>
      <td>00:01:26</td>
      <td>&nbsp;</td>
      <td></td>
    </tr>
  </tbody>
</table>
"""


def test_parse_transactions_table_normalizes_rows():
    rows = parsers.parse_transactions_table(TABLE_HTML)

    assert len(rows) == 3
    assert rows[0].vehicle == "Siloking 2022"
    assert rows[0].driver == "Jeffrey"
    assert rows[0].start_date_time == datetime(2022, 8, 23, 10, 30, 38)
    assert rows[0].transaction_number == "001012235085"
    assert rows[0].quantity_liters == 87.47
    assert rows[0].transaction_duration_seconds == 67
    assert rows[0].meter_value == 271
    assert rows[0].meter_type == "h"

    assert rows[1].meter_value == 370187
    assert rows[1].meter_type == "km"

    assert rows[2].meter_value is None
    assert rows[2].meter_type is None


def test_parse_transactions_table_uses_current_header_order():
    html = """
    <table>
      <tbody>
        <tr>
          <td>Driver</td>
          <td>Vehicle</td>
          <td>Product</td>
          <td>Quantity</td>
          <td>Start date-time</td>
          <td>Transaction number</td>
          <td>Transaction duration</td>
          <td>Meter</td>
        </tr>
        <tr>
          <td>Jeffrey</td>
          <td>Siloking 2022</td>
          <td>Diesel</td>
          <td>87.47&nbsp;L</td>
          <td>23/08/2022&nbsp;10:30:38</td>
          <td>001012235085</td>
          <td>00:01:07</td>
          <td>271&nbsp;h</td>
        </tr>
      </tbody>
    </table>
    """

    rows = parsers.parse_transactions_table(html)

    assert len(rows) == 1
    assert rows[0].driver == "Jeffrey"
    assert rows[0].vehicle == "Siloking 2022"
    assert rows[0].product == "Diesel"
    assert rows[0].transaction_number == "001012235085"
