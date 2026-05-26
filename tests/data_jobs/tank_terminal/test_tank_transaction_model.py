from datetime import date, datetime

from database.models.tank_transaction import TankTransaction


def test_tank_transaction_accepts_csv_export_fields():
    transaction = TankTransaction.model_validate(
        {
            "transaction_number": "001012235085",
            "dispenser": "Dieselpomp",
            "tank": "Diesel",
            "vehicle": "Siloking",
            "vehicle_number": "123",
            "driver": "Magnus",
            "driver_number": "7",
            "product": "Diesel",
            "transaction_type": "Dispensing",
            "transaction_result": "Authorised",
            "acquisition_mode": "Key",
            "transaction_status": "Normal",
            "start_date_time": datetime(2026, 5, 26, 6, 36, 20),
            "transaction_date": date(2026, 5, 26),
            "transaction_hour": "06:36",
            "quantity_liters": 84.34,
            "quantity_units": "L",
            "transaction_duration_seconds": 91,
            "odometer": 12345.0,
            "hours_counter": 271.0,
            "meter_value": 271.0,
            "meter_type": "h",
            "vehicle_identifier": "V-ID",
            "driver_identifier": "D-ID",
        }
    )

    assert transaction.transaction_number == "001012235085"
    assert transaction.quantity_liters == 84.34
    assert transaction.hours_counter == 271.0
    assert transaction.transaction_date == date(2026, 5, 26)
