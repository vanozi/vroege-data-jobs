from database.persistence import tank_terminal


class FakeTankTransactionsRepository:
    def __init__(self):
        self.rows = []
        self.rows_by_start_date_time = []

    def upsert_tank_transaction(self, row):
        self.rows.append(row)

    def upsert_tank_transaction_by_start_date_time(self, row):
        self.rows_by_start_date_time.append(row)


def test_save_tank_transactions_dry_run_without_repository():
    rows = [{"transaction_number": "001"}]

    saved_count = tank_terminal.save_tank_transactions(
        rows,
        repository=None,
        dry_run=True,
    )

    assert saved_count == 1


def test_save_tank_transactions_upserts_rows():
    repository = FakeTankTransactionsRepository()
    rows = [{"transaction_number": "001"}, {"transaction_number": "002"}]

    saved_count = tank_terminal.save_tank_transactions(
        rows,
        repository=repository,
    )

    assert saved_count == 2
    assert repository.rows == rows


def test_save_tank_transaction_models_by_start_date_time_upserts_rows():
    repository = FakeTankTransactionsRepository()
    rows = [{"start_date_time": "2026-05-26T08:15:55"}]

    saved_count = tank_terminal.save_tank_transaction_models_by_start_date_time(
        rows,
        repository=repository,
    )

    assert saved_count == 1
    assert repository.rows_by_start_date_time == rows
