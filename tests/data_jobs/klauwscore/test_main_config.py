from data_jobs.klauwscore import main


def test_main_wrapper_delegates_to_collect_cli(monkeypatch):
    called = []

    monkeypatch.setattr(
        main.collect_klauwscore,
        "main",
        lambda: called.append("collect"),
    )

    main.main()

    assert called == ["collect"]
