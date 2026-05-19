from data_jobs.uniform_agri.api_client import ApiClient
from data_jobs.uniform_agri import payloads, transforms
from data_jobs.uniform_agri.config import UniformAgriConfig
from typing import Optional
from datetime import datetime as dt

from database.models.koe import Koe, KoeDetail
from database.models.melking import Melking


class UniformService:
    """Service layer for Uniform API - orchestrates API calls and data transformation"""

    def __init__(
        self,
        client: Optional[ApiClient] = None,
        config: Optional[UniformAgriConfig] = None,
    ):
        self.client = client or ApiClient(config=config)

    def get_herd_registration(
        self,
        herd_id: str,
        date: Optional[dt] = None,
    ) -> list[Koe]:
        """
        Get all animals currently in the herd (herd registration)
        This is the starting point for data collection

        Args:
            herd_id: UUID of the herd
            date: Date for the registration (defaults to today)

        Returns:
            List of HerdRegistrationAnimal objects with basic animal info
        """
        return [
            transforms.koe_from_registration(raw)
            for raw in self.fetch_herd_registration(herd_id, date)
        ]

    def fetch_herd_registration(
        self,
        herd_id: str,
        date: Optional[dt] = None,
    ) -> list[dict]:
        """Fetch raw herd registration items from Uniform Agri."""
        endpoint = f"/herd/{herd_id}/management/form/herd/herdregistration"
        raw_data = self.client.post(
            endpoint,
            json=payloads.build_herd_registration_payload(herd_id, date),
        )
        return raw_data["itemList"]

    def get_actual_tab_data(self, herd_id: str, animal_id: str) -> KoeDetail:
        """
        Get actual tab data for a specific animal.

        This endpoint provides detailed current information about an animal including:
        - Lactation information (DIM, milk yield)
        - Reproduction status
        - Body weight and condition
        - Group assignments
        - Full animal details

        Args:
            herd_id: UUID of the herd
            animal_id: UUID of the animal

        Returns:
            KoeDetail object with animal details from the 'animal' field in response
        """
        return transforms.koe_detail_from_actual(
            self.fetch_animal_actual(herd_id, animal_id)
        )

    def fetch_animal_actual(self, herd_id: str, animal_id: str) -> dict:
        """Fetch raw actual-tab data for one animal from Uniform Agri."""
        endpoint = (
            f"/herd/{herd_id}/management/form/animalrecord/{animal_id}/tab/actual"
        )
        return self.client.post(
            endpoint,
            json=payloads.build_animal_actual_payload(herd_id),
        )

    def get_milk_recordings(self, herd_id: str, animal_id: str) -> list[Melking]:
        """
        Get milk recording data (milkings) for a specific animal.

        This endpoint provides all milking records including:
        - Individual milking events with timestamps
        - Milk yield per milking
        - Milking speed and duration
        - Conductivity values for mastitis detection
        - Days in milk (DIM) at time of milking

        Args:
            herd_id: UUID of the herd
            animal_id: UUID of the animal

        Returns:
            List of Melking objects from the 'milkingList' field in response
        """
        return [
            transforms.melking_from_recording(raw)
            for raw in self.fetch_milk_recordings(herd_id, animal_id)
        ]

    def fetch_milk_recordings(self, herd_id: str, animal_id: str) -> list[dict]:
        """Fetch raw milk recording items for one animal from Uniform Agri."""
        endpoint = f"/herd/{herd_id}/management/form/animalrecord/{animal_id}/tab/milkrecording"
        raw_data = self.client.post(
            endpoint,
            json=payloads.build_milk_recordings_payload(herd_id),
        )
        return raw_data.get("milkingList", [])
