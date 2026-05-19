from data_jobs.klauwscore.scripts import collect_klauwscore


def main() -> None:
    """Compatibility wrapper for the Klauwscore collection CLI."""
    collect_klauwscore.main()


if __name__ == "__main__":
    main()
