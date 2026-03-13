
from models.koe import Koe, KoeDetail
from models.melking import Melking
from api_client import ApiClient
from typing import List
from datetime import datetime as dt
from uuid import UUID
from datetime import datetime


class UniformService:
    """Service layer for Uniform API - orchestrates API calls and data transformation"""

    def __init__(self, client: ApiClient = None):
        self.client = client or ApiClient()

    # Default payload for animal record requests
    DEFAULT_PAYLOAD = {
        "printClassification": True,
        "printGeneral": True,
        "printReproduction": True,
        "historicColor": 10526800,
        "cullingColor": 8421504,
        "descending": False,
        "showFarmName": False,
        "useHistoricColor": True,
        "useCullingColor": True,
        "printHealth": True,
        "startPage": 0,
        "printMovements": True,
        "printMilkTestAll": True,
        "showYoungStockAgeInWeeks": False,
        "printCondition": True,
        "printLactation": True,
        "printReproductionAll": True,
        "defaultMilkRecKind": "MilkMeter",
        "printMilkTest": True,
        "groupByHerd": False,
        "isOwner": False,
        "multiHerdLevel": "ActiveHerd",
        "kind": "Default",
        "name": "Default",
        "active": True,
    }


    def get_herd_registration(self, herd_id: str, date: str = None) -> List[Koe]:
        """
        Get all animals currently in the herd (herd registration)
        This is the starting point for data collection

        Args:
            herd_id: UUID of the herd
            date: Date for the registration (defaults to today)

        Returns:
            List of HerdRegistrationAnimal objects with basic animal info
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%dT00:00:00.0")

        payload = {
            "date": date,
            "herds": [{"id": herd_id}],
            "groupByHerd": False,
            "isOwner": False,
            "multiHerdLevel": "ActiveHerd",
            "presetLevel": "Company",
            "availablePresetLevels": ["Company", "Herd", "User"],
            "report": {
                "pageOrientation": "Default",
                "textFontSize": 8
            },
            "kind": "Default",
            "grids": [{
                "name": "GridHerdRegistration",
                "columns": [
                    {"index": 0, "name": "Herd", "width": 75, "visible": True},
                    {"index": 1, "name": "VolgNr", "width": 100, "visible": True},
                    {"index": 2, "name": "Number", "width": 100, "visible": True, "columnType": 1},
                    {"index": 3, "name": "Name", "width": 200, "visible": True, "columnType": 2},
                    {"index": 4, "name": "Eartag", "width": 150, "visible": True, "sortIndex": 0, "sortOrder": "asc", "columnType": 3},
                    {"index": 5, "name": "EartagShort", "width": 100, "visible": True, "columnType": 4},
                    {"index": 6, "name": "Sex", "width": 100, "visible": True},
                    {"index": 7, "name": "BirthDate", "width": 150, "visible": True},
                    {"index": 8, "name": "HairColor", "width": 100, "visible": True},
                    {"index": 9, "name": "DamEartag", "width": 100, "visible": True}
                ]
            }],
            "name": "Default",
            "active": True
        }

        endpoint = f"/herd/{herd_id}/management/form/herd/herdregistration"
        raw_data = self.client.post(endpoint, json=payload)

        if isinstance(raw_data, dict) and 'itemList' in raw_data:
            animals_list = raw_data['itemList']

            # Convert string UUIDs and datetimes to proper types
            for animal_data in animals_list:
                # Convert animalId from string to UUID
                if 'animalId' in animal_data and isinstance(animal_data['animalId'], str):
                    animal_data['animalId'] = UUID(animal_data['animalId'])

                # Convert birthDate from string to datetime
                if 'birthDate' in animal_data and isinstance(animal_data['birthDate'], str):
                    v = animal_data['birthDate'].replace('.0', '') if animal_data['birthDate'].endswith('.0') else animal_data['birthDate']
                    animal_data['birthDate'] = dt.fromisoformat(v)

        return [Koe(**animal) for animal in animals_list]

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
        payload = {
            **self.DEFAULT_PAYLOAD,
            "herds": [{"id": herd_id}],
        }

        endpoint = f"/herd/{herd_id}/management/form/animalrecord/{animal_id}/tab/actual"
        raw_data = self.client.post(endpoint, json=payload)
        extracted_data = {}

        # The response contains an 'animal' field with all the detail data
        if isinstance(raw_data, dict) and 'animal' in raw_data:
            animal = raw_data.pop('animal')  # Remove 'animal' from dict
            extracted_data = {
                **raw_data,  # Root-level properties
                'animalId': UUID(animal['animalId']),
                'previousNumber': animal.get('previousNumber'),
                'transponder1': animal.get('transponder1'),
                'feedingGroupName': animal.get('feedingGroupName'),
                'feedingGroupNumber': animal.get('feedingGroupNumber'),
                'barnGroupName': animal.get('barnGroupName'),
                'barnGroupNumber': animal.get('barnGroupNumber'),
                'animalType': animal.get('animalType'),
                'animalTypeText': animal.get('animalTypeText'),
                'herdName': animal.get('herdName'),
                'lastHerdId': UUID(animal['lastHerdId']) if 'lastHerdId' in animal and isinstance(animal['lastHerdId'], str) else None,
                'isDead': animal.get('isDead'),
                'isYoungStock': animal.get('isYoungStock'),
                'toBeCulled': animal.get('toBeCulled'),
                'aborted': animal.get('aborted'),
                'barren': animal.get('barren'),
                'isBeef': animal.get('isBeef'),
                'dam': animal.get('dam'),
                'sire': animal.get('sire'),
                'breedText': animal.get('breedText'),
                'age': animal.get('age'),
                'longName': animal.get('longName'),
                'comment': animal.get('comment'),
            }


        return KoeDetail(**extracted_data)

    def get_milk_recordings(self, herd_id: str, animal_id: str) -> List[Melking]:
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
        payload = {
            **self.DEFAULT_PAYLOAD,
            "selectedMilkKind": "MilkMeter",
            "showAllDates": False,
            "herds": [{"id": herd_id}],
        }

        endpoint = f"/herd/{herd_id}/management/form/animalrecord/{animal_id}/tab/milkrecording"
        raw_data = self.client.post(endpoint, json=payload)

        # The response contains a 'milkingList' field with all milking records
        if isinstance(raw_data, dict) and 'milkingList' in raw_data:
            milking_list = raw_data['milkingList']

            # Convert string UUIDs and datetimes to proper types
            for milking_data in milking_list:
                # Convert UUID fields
                for uuid_field in ['id', 'herdId', 'animalId']:
                    if uuid_field in milking_data and isinstance(milking_data[uuid_field], str):
                        milking_data[uuid_field] = UUID(milking_data[uuid_field])

                # Convert datetime fields
                for datetime_field in ['shiftDate', 'dateTime']:
                    if datetime_field in milking_data and isinstance(milking_data[datetime_field], str):
                        v = milking_data[datetime_field].replace('.0', '') if milking_data[datetime_field].endswith('.0') else milking_data[datetime_field]
                        milking_data[datetime_field] = dt.fromisoformat(v)

            return [Melking(**milking) for milking in milking_list]
