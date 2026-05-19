import json

from data_jobs.klauwscore.collectors import KlauwscoreCollectionResult


def serialize_documents(result: KlauwscoreCollectionResult) -> str:
    """Serialize grouped documents to JSON."""
    data = []
    for document in result.documents:
        data.append(
            {
                "behandeldatum": document.behandeldatum.isoformat(),
                "aantal_koeien": document.aantal_koeien,
                "href": document.href,
                "records": [
                    {
                        "behandeldatum": record.behandeldatum.isoformat(),
                        "halsbandnummer": record.halsbandnummer,
                        "notities": record.notities,
                    }
                    for record in document.records
                ],
            }
        )

    return json.dumps(data, ensure_ascii=False, indent=2)


def serialize_flat_rows(rows: list[dict[str, object]]) -> str:
    """Serialize flattened rows to JSON."""
    data = []
    for row in rows:
        data.append(
            {
                **row,
                "behandeldatum": row["behandeldatum"].isoformat(),
            }
        )

    return json.dumps(data, ensure_ascii=False, indent=2)


def summary_lines(
    result: KlauwscoreCollectionResult,
    saved_klauw_behandelingen: int,
    dry_run: bool,
) -> list[str]:
    """Build intentional CLI summary output lines."""
    counts = result.summary_counts()
    lines = [
        f"documents={counts['documents']}",
        f"cow_records={counts['cow_records']}",
        f"notitie_rows={counts['notitie_rows']}",
        f"deduped_notitie_rows={counts['deduped_notitie_rows']}",
        f"duplicate_rows={counts['duplicate_rows']}",
        f"count_mismatches={counts['count_mismatches']}",
        f"failures={counts['failures']}",
        f"saved_klauw_behandelingen={saved_klauw_behandelingen}",
        f"dry_run={dry_run}",
    ]

    for mismatch in result.count_mismatches[:10]:
        lines.append(
            "count_mismatch="
            f"{mismatch.behandeldatum} "
            f"agenda={mismatch.aantal_koeien} "
            f"parsed={mismatch.parsed_count} "
            f"{mismatch.href}"
        )

    for failure in result.failures[:10]:
        lines.append(
            "collection_failure="
            f"stage={failure.stage} "
            f"date={failure.behandeldatum} "
            f"href={failure.href} "
            f"error={failure.error}"
        )

    return lines
