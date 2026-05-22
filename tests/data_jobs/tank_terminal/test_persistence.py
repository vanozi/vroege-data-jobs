from database.persistence import tank_terminal


class FakeTankTransactionsRepository:
    def __init__(self):
        self.rows = []

    def upsert_tank_transaction(self, row):
        self.rows.append(row)


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
