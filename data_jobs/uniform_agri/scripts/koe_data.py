"""
Example usage of the structured Uniform API client

This demonstrates the clean separation of concerns:
- ApiClient: Raw HTTP requests
- Models: Data validation and transformation
- UniformService: Business logic orchestration
- DatabaseManager: Data persistence

Flow:
1. Get herd registration (all animals in stable)
2. For each animal, fetch detailed data
3. Store in database
"""


from database.repositories.melkingen_repository import MelkingenRepository
from data_jobs.uniform_agri.services.uniform_service import UniformService
from database.database import init_db, get_session
from repositories import KoeRepository
from database.repositories.koe_detail_repository import KoeDetailRepository
from data_jobs.uniform_agri.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    # Initialize database (creates tables if they don't exist)
    init_db()

    # Initialize service and repository
    service = UniformService()
    koe_repo = KoeRepository(get_session)
    koe_detail_repo = KoeDetailRepository(get_session)

    # Configuration
    herd_id = "c670836f-7732-43a1-ac5a-70c4f63435f4"

    print("Start met data collectie.")
    print("=" * 60)

    # Step 1: Get all animals in the herd (starting point)
    print("\nStep 1: Stallijst ophalen ...")
    try:
        koeien = service.get_herd_registration(herd_id)
        print(f"{len(koeien)} koeien op de stallijst")

    except Exception as e:
        print(f"Error fetching herd registration: {e}")
        return

    # Step 2: Insert animals into database
    print("\nStep 2: Inserting data into tables...")
    logger.info("Starting data insertion for %d animals", len(koeien))

    # Track animal IDs that are in the current herd
    current_herd_animal_ids = []

    for koe in koeien:
        if koe.name and koe.name.upper().startswith("VAARSKALF") or koe.name.upper().startswith("STIERKALF"):
            continue

        # Insert Koe
        try:
            print(f"Inserting Koe: {koe.name} ({koe.eartag})")
            koe_repo.upsert_koe(koe)
            current_herd_animal_ids.append(koe.animal_id)
            print(f"Inserted Koe: {koe.name} ({koe.eartag})")
            logger.info("Successfully inserted Koe: %s (%s)", koe.name, koe.eartag)
        except Exception as e:
            logger.error("Failed to insert Koe: %s (%s) - Error: %s", koe.name, koe.eartag, str(e), exc_info=True)
            continue  # Skip to next animal if koe insert fails

        # Insert Koe Details
        try:
            koe_detail = service.get_actual_tab_data(herd_id, koe.animal_id)
            print(f"  Inserting details for {koe.name}")
            koe_detail_repo.upsert_koe_detail(koe_detail)
            print(f"  Inserted details for {koe.name}")
            logger.info("Successfully inserted details for: %s", koe.name)
        except Exception as e:
            logger.error("Failed to insert details for: %s - Error: %s", koe.name, str(e), exc_info=True)
            # Continue to melkingen even if details fail

    # Step 3: Mark animals not in current herd
    print("\nStep 3: Marking animals not in current herd...")
    try:
        marked_count = koe_repo.mark_all_not_in_herd(current_herd_animal_ids)
        print(f"Marked {marked_count} animals as not in current herd")
        logger.info("Marked %d animals as not in current herd", marked_count)
    except Exception as e:
        logger.error("Failed to mark animals not in herd - Error: %s", str(e), exc_info=True)

    print("\nData collection completed!")



if __name__ == "__main__":
    main()
