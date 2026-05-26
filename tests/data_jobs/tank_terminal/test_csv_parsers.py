from datetime import date, datetime

import pytest

from data_jobs.tank_terminal import csv_parsers
from data_jobs.tank_terminal.csv_parsers import TankTerminalCsvParseError


CSV_EXPORT = """Terminal;Terminal - Terminal number;Product;Product - DiaLOG product code;Dispenser;Dispenser - Number;Dispensing point - Nozzle number;Tank;Tank - Number;Vehicle;Vehicle - Number;Vehicle - Vehicle registration;Vehicle - Manufacturer;Vehicle - Manufacturer model;Vehicle attachment site;Vehicle - Garage number;Vehicle - Fleet input date;Vehicle - Fleet output date;Vehicle - Revocation date;Vehicle - Status;Vehicle - Vehicle Identification Number;Vehicles type;Vehicles category;Driver;Driver - Number;Driver - First Name;Driver - Name;Driver attachment site;Driver - Status;Transaction number;Site;Start date-time;Transaction date;Transaction hour;Quantity;Quantity - Units;Transaction duration;Transaction duration - Units;Maximum authorised quantity;Maximum authorised quantity - Units;Comment;Odometer;Odometer - Units;Hours counter;Hours counter - Units;Start odometer;Start odometer - Units;End odometer;End odometer - Units;Start hours meter;Start hours meter - Units;End hours meter;End hours meter - Units;Reference consumption;Reference consumption - Units;Minimal consumption;Minimal consumption - Units;Maximal consumption;Maximal consumption - Units;Inverse reference consumption;Inverse minimal consumption;Inverse maximal consumption;Service;Service - Number;Service - Comment;Department;Amount;Amount - Units;Unit price;Unit price - Units;External site;External site - Address;External site - Address (continue);External site - Post Code;External site - City;External site - Comment;External site - Department (TICPE);Acquisition mode;Transaction status;Transaction type;Transaction result;Vehicle identifier;Driver identifier;Week;Month;Anomaly(ies) (if only transactions with anomalies)
Loonbedrijf Vroege Dalen;1;Diesel;1;Pomp 2 diesel;2;1;Tank 1 Diesel;1;Jan's Bus;76;;;;Loonbedrijf Vroege;;29/08/2022;;;Authorised;67;;;Jan Vroege;28;;Jan Vroege;Loonbedrijf Vroege;Authorised;001016145323;Loonbedrijf Vroege;25/05/2026 08:15:55;25/05/2026;08:15:55;49,24;L;1,52;min;0,00;L;;;;;;;;;;;;;;;;;;;;;;;;;;;0,00;€;0,000;€/L;;;;;;;;Normal;Normal;Dispensing;Successful;67;2908;22;5;
Loonbedrijf Vroege Dalen;1;Diesel;1;Pomp 2 diesel;2;1;Tank 1 Diesel;1;Zwarte Kramer;56;;;;Loonbedrijf Vroege;;13/04/2022;;;Authorised;;;;Ellen Vroege;4;;Ellen Vroege;Loonbedrijf Vroege;Authorised;001016145324;Loonbedrijf Vroege;25/05/2026 09:32:25;25/05/2026;09:32:25;48,67;L;1,22;min;0,00;L;;;;1;h;;;;;;;;;;;;;;;;;;;;;;0,00;€;0,000;€/L;;;;;;;;Normal;Normal;Dispensing;Successful;53;1508;22;5;
"""


def test_parse_tank_transactions_csv_text_maps_selected_export_fields():
    transactions = csv_parsers.parse_tank_transactions_csv_text(CSV_EXPORT)

    assert len(transactions) == 2

    first = transactions[0]
    assert first.transaction_number == "001016145323"
    assert first.start_date_time == datetime(2026, 5, 25, 8, 15, 55)
    assert first.transaction_date == date(2026, 5, 25)
    assert first.transaction_hour == "08:15:55"
    assert first.vehicle == "Jan's Bus"
    assert first.vehicle_number == "76"
    assert first.driver == "Jan Vroege"
    assert first.driver_number == "28"
    assert first.product == "Diesel"
    assert first.quantity_liters == 49.24
    assert first.quantity_units == "L"
    assert first.dispenser == "Pomp 2 diesel"
    assert first.tank == "Tank 1 Diesel"
    assert first.odometer is None
    assert first.hours_counter is None
    assert first.acquisition_mode == "Normal"
    assert first.transaction_status == "Normal"
    assert first.transaction_type == "Dispensing"
    assert first.transaction_result == "Successful"
    assert first.vehicle_identifier == "67"
    assert first.driver_identifier == "2908"
    assert first.meter_value is None
    assert first.meter_type is None

    second = transactions[1]
    assert second.hours_counter == 1
    assert second.meter_value == 1
    assert second.meter_type == "h"


def test_parse_tank_transactions_csv_text_reports_row_number_for_bad_data():
    csv_text = CSV_EXPORT.replace("49,24", "", 1)

    with pytest.raises(TankTerminalCsvParseError, match="row 2"):
        csv_parsers.parse_tank_transactions_csv_text(csv_text)
