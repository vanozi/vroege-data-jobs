from datetime import datetime

from data_jobs.uniform_agri.services.uniform_service import UniformService


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def post(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        return self.responses[endpoint]


def test_fetch_herd_registration_returns_raw_items_and_payload():
    endpoint = "/herd/herd-id/management/form/herd/herdregistration"
    client = FakeClient({endpoint: {"itemList": [{"animalId": "animal-id"}]}})
    service = UniformService(client=client)

    result = service.fetch_herd_registration(
        "herd-id",
        datetime(2026, 5, 19),
    )

    assert result == [{"animalId": "animal-id"}]
    assert client.calls[0][0] == endpoint
    assert client.calls[0][1]["json"]["date"] == "2026-05-19T00:00:00.0"
    assert client.calls[0][1]["json"]["herds"] == [{"id": "herd-id"}]
    assert client.calls[0][1]["json"]["accessHerds"] == ["herd-id"]


def test_fetch_animal_actual_returns_raw_response_and_payload():
    endpoint = "/herd/herd-id/management/form/animalrecord/animal-id/tab/actual"
    response = {"animal": {"animalId": "animal-id"}}
    client = FakeClient({endpoint: response})
    service = UniformService(client=client)

    result = service.fetch_animal_actual("herd-id", "animal-id")

    assert result == response
    assert client.calls[0][0] == endpoint
    assert client.calls[0][1]["json"]["herds"] == [{"id": "herd-id"}]
    assert client.calls[0][1]["json"]["accessHerds"] == ["herd-id"]


def test_fetch_milk_recordings_returns_raw_items_and_payload():
    endpoint = "/herd/herd-id/management/form/animalrecord/animal-id/tab/milkrecording"
    client = FakeClient({endpoint: {"milkingList": [{"id": "milking-id"}]}})
    service = UniformService(client=client)

    result = service.fetch_milk_recordings("herd-id", "animal-id")

    assert result == [{"id": "milking-id"}]
    assert client.calls[0][0] == endpoint
    assert client.calls[0][1]["json"]["selectedMilkKind"] == "MilkMeter"


def test_fetch_milk_recordings_returns_empty_list_when_response_has_no_milking_list():
    endpoint = "/herd/herd-id/management/form/animalrecord/animal-id/tab/milkrecording"
    client = FakeClient({endpoint: {}})
    service = UniformService(client=client)

    result = service.fetch_milk_recordings("herd-id", "animal-id")

    assert result == []
