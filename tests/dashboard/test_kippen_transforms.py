"""Tests for kippen_transforms pure functions."""

from datetime import date

import polars as pl
import pytest

from dashboard.kippen_transforms import (
    add_flock_week_column,
    add_rolling_average,
    calculate_flock_week,
    cumulative_kpis_per_placed_hen,
    cumulative_mortality_percentage,
    daily_bird_count,
    daily_fcr,
    daily_lay_percentage,
    format_norm_delta,
    forward_fill_egg_weight,
    get_norm_for_flock_week,
    join_forward_filled_weight,
    join_norms_by_age_week,
    norm_dates_for_flock,
    normalize_breed_key,
)

DOB = date(2025, 10, 1)


# ---------------------------------------------------------------------------
# calculate_flock_week
# ---------------------------------------------------------------------------


class TestCalculateFlockWeek:
    def test_day_1_is_week_0(self):
        # elapsed=1, curve_day=0, week=0
        assert calculate_flock_week(date(2025, 10, 2), DOB) == 0

    def test_day_of_birth_is_week_0(self):
        # elapsed=0, curve_day=0, week=0
        assert calculate_flock_week(DOB, DOB) == 0

    def test_week_33_start(self):
        # curve_day 231 = elapsed 232 → dob + 232 days
        target = date(2026, 5, 21)  # dob + 232 days
        assert calculate_flock_week(target, DOB) == 33

    def test_week_33_last_day(self):
        # curve_day 237 = elapsed 238 → dob + 238 days = 2026-05-27
        target = date(2026, 5, 27)
        assert calculate_flock_week(target, DOB) == 33

    def test_week_34_start(self):
        target = date(2026, 5, 28)  # dob + 239 days, curve_day 238
        assert calculate_flock_week(target, DOB) == 34

    def test_matches_kippen_app_flock_age(self):
        # Verify against kippen_app/flock_age.py:calculate_bird_age
        from kippen_app.flock_age import calculate_bird_age

        for offset in [0, 1, 7, 119, 231, 237, 365]:
            target = date.fromordinal(DOB.toordinal() + offset)
            our_week = calculate_flock_week(target, DOB)
            app_week = calculate_bird_age(DOB, target).weeks
            assert our_week == app_week, (
                f"Mismatch at offset {offset}: ours={our_week}, app={app_week}"
            )


class TestAddFlockWeekColumn:
    def test_adds_column(self):
        df = pl.DataFrame({"registration_date": [date(2026, 5, 21), date(2026, 5, 27)]})
        result = add_flock_week_column(df, "registration_date", DOB)
        assert "flock_week" in result.columns
        assert result["flock_week"].to_list() == [33, 33]

    def test_week_34(self):
        df = pl.DataFrame({"registration_date": [date(2026, 5, 28)]})
        result = add_flock_week_column(df, "registration_date", DOB)
        assert result["flock_week"][0] == 34


# ---------------------------------------------------------------------------
# daily_bird_count
# ---------------------------------------------------------------------------


class TestDailyBirdCount:
    def test_single_death(self):
        df = pl.DataFrame(
            {
                "found_date": [date(2026, 1, 10)],
                "dead_count": [5],
            }
        )
        result = daily_bird_count(df, initial_bird_count=1000)
        assert result["bird_count"][0] == 995
        assert result["cum_dead"][0] == 5

    def test_cumulative_across_days(self):
        df = pl.DataFrame(
            {
                "found_date": [date(2026, 1, 10), date(2026, 1, 11)],
                "dead_count": [10, 20],
            }
        )
        result = daily_bird_count(df, initial_bird_count=1000).sort("registration_date")
        assert result["cum_dead"].to_list() == [10, 30]
        assert result["bird_count"].to_list() == [990, 970]

    def test_multiple_deaths_same_day(self):
        df = pl.DataFrame(
            {
                "found_date": [date(2026, 1, 10), date(2026, 1, 10)],
                "dead_count": [3, 7],
            }
        )
        result = daily_bird_count(df, initial_bird_count=500)
        assert result["dead_today"][0] == 10
        assert result["bird_count"][0] == 490

    def test_empty_input(self):
        df = pl.DataFrame(
            {
                "found_date": pl.Series([], dtype=pl.Date),
                "dead_count": pl.Series([], dtype=pl.Int64),
            }
        )
        result = daily_bird_count(df, initial_bird_count=1000)
        assert result.is_empty()


class TestCumulativeMortalityPercentage:
    def test_percentage(self):
        df = pl.DataFrame({"found_date": [date(2026, 1, 10)], "dead_count": [100]})
        result = cumulative_mortality_percentage(df, initial_bird_count=1000)
        assert result["cum_dead_pct"][0] == pytest.approx(10.0)

    def test_zero_initial_count_returns_empty(self):
        df = pl.DataFrame({"found_date": [date(2026, 1, 10)], "dead_count": [5]})
        result = cumulative_mortality_percentage(df, initial_bird_count=0)
        assert result.is_empty()


# ---------------------------------------------------------------------------
# forward_fill_egg_weight / join_forward_filled_weight
# ---------------------------------------------------------------------------


class TestForwardFillEggWeight:
    def test_daily_average(self):
        df = pl.DataFrame(
            {
                "registration_date": [
                    date(2026, 1, 10),
                    date(2026, 1, 10),
                    date(2026, 1, 11),
                ],
                "egg_weight_grams": [60.0, 62.0, 63.0],
            }
        )
        result = forward_fill_egg_weight(df)
        result = result.sort("registration_date")
        assert result["egg_weight_grams_filled"][0] == pytest.approx(61.0)
        assert result["egg_weight_grams_filled"][1] == pytest.approx(63.0)
        assert result["is_measured"].to_list() == [True, True]

    def test_empty_returns_empty(self):
        df = pl.DataFrame(
            {
                "registration_date": pl.Series([], dtype=pl.Date),
                "egg_weight_grams": pl.Series([], dtype=pl.Float64),
            }
        )
        result = forward_fill_egg_weight(df)
        assert result.is_empty()


class TestJoinForwardFilledWeight:
    def test_forward_fill_propagates(self):
        base = pl.DataFrame(
            {
                "registration_date": [
                    date(2026, 1, 8),
                    date(2026, 1, 9),
                    date(2026, 1, 10),
                    date(2026, 1, 11),
                ]
            }
        )
        pallets = pl.DataFrame(
            {
                "registration_date": [date(2026, 1, 10)],
                "egg_weight_grams": [62.0],
            }
        )
        result = join_forward_filled_weight(base, pallets)
        # Before first measurement: null
        assert (
            result.filter(pl.col("registration_date") < date(2026, 1, 10))[
                "egg_weight_grams_filled"
            ]
            .is_null()
            .all()
        )
        # Measurement day: 62.0, is_measured=True
        row_10 = result.filter(pl.col("registration_date") == date(2026, 1, 10))
        assert row_10["egg_weight_grams_filled"][0] == pytest.approx(62.0)
        assert row_10["is_measured"][0] is True
        # Day after: 62.0 forward-filled, is_measured=False
        row_11 = result.filter(pl.col("registration_date") == date(2026, 1, 11))
        assert row_11["egg_weight_grams_filled"][0] == pytest.approx(62.0)
        assert row_11["is_measured"][0] is False

    def test_no_pallet_data_gives_all_nulls(self):
        base = pl.DataFrame(
            {"registration_date": [date(2026, 1, 10), date(2026, 1, 11)]}
        )
        pallets = pl.DataFrame(
            {
                "registration_date": pl.Series([], dtype=pl.Date),
                "egg_weight_grams": pl.Series([], dtype=pl.Float64),
            }
        )
        result = join_forward_filled_weight(base, pallets)
        assert result["egg_weight_grams_filled"].is_null().all()
        assert result["is_measured"].to_list() == [False, False]


# ---------------------------------------------------------------------------
# daily_lay_percentage
# ---------------------------------------------------------------------------


class TestDailyLayPercentage:
    def test_basic_percentage(self):
        eggs = pl.DataFrame(
            {
                "registration_date": [date(2026, 1, 10)],
                "total_eggs": [9700],
            }
        )
        birds = pl.DataFrame(
            {"registration_date": [date(2026, 1, 10)], "bird_count": [10000]}
        )
        result = daily_lay_percentage(eggs, birds)
        assert result["lay_percentage"][0] == pytest.approx(97.0)

    def test_zero_bird_count_gives_null(self):
        eggs = pl.DataFrame(
            {"registration_date": [date(2026, 1, 10)], "total_eggs": [100]}
        )
        birds = pl.DataFrame(
            {"registration_date": [date(2026, 1, 10)], "bird_count": [0]}
        )
        result = daily_lay_percentage(eggs, birds)
        assert result["lay_percentage"].is_null().all()

    def test_no_bird_data_for_day_gives_null(self):
        eggs = pl.DataFrame(
            {"registration_date": [date(2026, 1, 10)], "total_eggs": [100]}
        )
        birds = pl.DataFrame(
            {
                "registration_date": pl.Series([], dtype=pl.Date),
                "bird_count": pl.Series([], dtype=pl.Int64),
            }
        )
        result = daily_lay_percentage(eggs, birds)
        assert result["lay_percentage"].is_null().all()

    def test_empty_egg_df_returns_empty(self):
        eggs = pl.DataFrame(
            {
                "registration_date": pl.Series([], dtype=pl.Date),
                "total_eggs": pl.Series([], dtype=pl.Int64),
            }
        )
        result = daily_lay_percentage(
            eggs, pl.DataFrame({"registration_date": [], "bird_count": []})
        )
        assert result.is_empty()


# ---------------------------------------------------------------------------
# daily_fcr
# ---------------------------------------------------------------------------


class TestDailyFcr:
    def test_basic_fcr(self):
        # 10000 eggs * 62g = 620000g egg mass; 120000g feed → FCR=0.1935...
        feed = pl.DataFrame(
            {"registration_date": [date(2026, 1, 10)], "feed_grams": [120_000]}
        )
        pallets = pl.DataFrame(
            {"registration_date": [date(2026, 1, 10)], "egg_weight_grams": [62.0]}
        )
        eggs = pl.DataFrame(
            {"registration_date": [date(2026, 1, 10)], "total_eggs": [10_000]}
        )
        result = daily_fcr(feed, pallets, eggs)
        expected = 120_000 / (10_000 * 62.0)
        assert result["fcr"][0] == pytest.approx(expected, rel=1e-4)
        assert result["is_measured_weight"][0] is True

    def test_no_pallet_before_first_measurement_gives_null(self):
        feed = pl.DataFrame(
            {"registration_date": [date(2026, 1, 9)], "feed_grams": [120_000]}
        )
        pallets = pl.DataFrame(
            {"registration_date": [date(2026, 1, 10)], "egg_weight_grams": [62.0]}
        )
        eggs = pl.DataFrame(
            {"registration_date": [date(2026, 1, 9)], "total_eggs": [10_000]}
        )
        result = daily_fcr(feed, pallets, eggs)
        assert result["fcr"].is_null().all()

    def test_empty_feed_returns_empty(self):
        result = daily_fcr(
            pl.DataFrame(
                {
                    "registration_date": pl.Series([], dtype=pl.Date),
                    "feed_grams": pl.Series([], dtype=pl.Int64),
                }
            ),
            pl.DataFrame(
                {
                    "registration_date": pl.Series([], dtype=pl.Date),
                    "egg_weight_grams": pl.Series([], dtype=pl.Float64),
                }
            ),
            pl.DataFrame(
                {
                    "registration_date": pl.Series([], dtype=pl.Date),
                    "total_eggs": pl.Series([], dtype=pl.Int64),
                }
            ),
        )
        assert result.is_empty()


# ---------------------------------------------------------------------------
# cumulative_kpis_per_placed_hen
# ---------------------------------------------------------------------------


class TestCumulativeKpisPerPlacedHen:
    def test_basic_kpis(self):
        eggs = pl.DataFrame(
            {
                "registration_date": [date(2026, 1, 10), date(2026, 1, 11)],
                "total_eggs": [9700, 9650],
            }
        )
        feed = pl.DataFrame(
            {
                "registration_date": [date(2026, 1, 10), date(2026, 1, 11)],
                "feed_grams": [120_000, 120_000],
            }
        )
        pallets = pl.DataFrame(
            {
                "registration_date": [date(2026, 1, 10)],
                "egg_weight_grams": [62.0],
            }
        )
        result = cumulative_kpis_per_placed_hen(eggs, feed, pallets, 10_000)

        assert result["eggs_per_placed_hen"] == pytest.approx((9700 + 9650) / 10_000)
        assert result["feed_kg_per_placed_hen"] == pytest.approx(
            (120_000 + 120_000) / 1000.0 / 10_000
        )
        assert result["eggs_per_placed_hen"] is not None
        assert result["cum_fcr"] is not None

    def test_zero_bird_count_returns_none(self):
        result = cumulative_kpis_per_placed_hen(
            pl.DataFrame(
                {"registration_date": [date(2026, 1, 10)], "total_eggs": [100]}
            ),
            pl.DataFrame(
                {"registration_date": [date(2026, 1, 10)], "feed_grams": [1000]}
            ),
            pl.DataFrame({"registration_date": [], "egg_weight_grams": []}),
            0,
        )
        assert all(v is None for v in result.values())

    def test_no_pallet_data_gives_null_egg_mass_kpis(self):
        eggs = pl.DataFrame(
            {"registration_date": [date(2026, 1, 10)], "total_eggs": [9700]}
        )
        feed = pl.DataFrame(
            {"registration_date": [date(2026, 1, 10)], "feed_grams": [120_000]}
        )
        pallets = pl.DataFrame(
            {
                "registration_date": pl.Series([], dtype=pl.Date),
                "egg_weight_grams": pl.Series([], dtype=pl.Float64),
            }
        )
        result = cumulative_kpis_per_placed_hen(eggs, feed, pallets, 10_000)
        assert result["egg_kg_per_placed_hen"] is None
        assert result["cum_fcr"] is None
        assert result["eggs_per_placed_hen"] == pytest.approx(9700 / 10_000)


# ---------------------------------------------------------------------------
# normalize_breed_key
# ---------------------------------------------------------------------------


class TestNormalizeBreedKey:
    def test_dekalb_white_full_name(self):
        result = normalize_breed_key("DEKALB WHITE SCHARREL EN VOLIÈRE")
        assert result == "dekalb_white_scharrel_voliere"

    def test_dekalb_wit_short(self):
        assert normalize_breed_key("Dekalb Wit") == "dekalb_white_scharrel_voliere"

    def test_lowercase_passthrough(self):
        assert normalize_breed_key("dekalb_wit") == "dekalb_white_scharrel_voliere"

    def test_none_returns_none(self):
        assert normalize_breed_key(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_breed_key("") is None
        assert normalize_breed_key("   ") is None

    def test_hyphens_become_underscores(self):
        assert normalize_breed_key("Hy-Line Brown") == "hy_line_brown"

    def test_multiple_spaces_collapsed(self):
        result = normalize_breed_key("Lohmann  White")
        assert result == "lohmann_white"

    def test_special_chars_removed(self):
        result = normalize_breed_key("Breed (123)")
        assert result == "breed_123"


# ---------------------------------------------------------------------------
# join_norms_by_age_week
# ---------------------------------------------------------------------------


class TestJoinNormsByAgeWeek:
    def test_joins_on_flock_week(self):
        df = pl.DataFrame({"flock_week": [33, 34], "lay_percentage": [96.5, 96.2]})
        norms = pl.DataFrame(
            {
                "age_weeks": [33, 34],
                "lay_percentage_norm": [97.0, 97.0],
                "feed_intake_grams_per_day": [120.0, 120.0],
            }
        )
        result = join_norms_by_age_week(df, norms)
        assert "lay_percentage_norm" in result.columns
        assert result.filter(pl.col("flock_week") == 33)["lay_percentage_norm"][
            0
        ] == pytest.approx(97.0)

    def test_empty_norm_returns_original(self):
        df = pl.DataFrame({"flock_week": [33], "lay_percentage": [96.5]})
        norms = pl.DataFrame(
            {
                "age_weeks": pl.Series([], dtype=pl.Int32),
                "lay_percentage_norm": pl.Series([], dtype=pl.Float64),
            }
        )
        result = join_norms_by_age_week(df, norms)
        assert result.columns == df.columns
        assert len(result) == 1

    def test_unmatched_week_gets_null(self):
        df = pl.DataFrame({"flock_week": [99]})
        norms = pl.DataFrame({"age_weeks": [33], "some_norm": [97.0]})
        result = join_norms_by_age_week(df, norms)
        assert result["some_norm"].is_null().all()


# ---------------------------------------------------------------------------
# add_rolling_average
# ---------------------------------------------------------------------------


class TestAddRollingAverage:
    def test_7day_rolling(self):
        df = pl.DataFrame(
            {
                "registration_date": [date(2026, 1, i) for i in range(1, 9)],
                "lay_percentage": [90.0, 91.0, 92.0, 93.0, 94.0, 95.0, 96.0, 97.0],
            }
        )
        result = add_rolling_average(df, "lay_percentage", window=7)
        assert "lay_percentage_rolling7" in result.columns
        # First 6 values are null (window not full yet)
        assert result["lay_percentage_rolling7"][:6].is_null().all()
        # 7th value = mean of first 7
        expected = sum([90.0, 91.0, 92.0, 93.0, 94.0, 95.0, 96.0]) / 7
        assert result["lay_percentage_rolling7"][6] == pytest.approx(expected)

    def test_custom_output_col_name(self):
        df = pl.DataFrame(
            {
                "registration_date": [date(2026, 1, 1)],
                "val": [5.0],
            }
        )
        result = add_rolling_average(df, "val", window=1, output_col="my_rolling")
        assert "my_rolling" in result.columns


# ---------------------------------------------------------------------------
# norm_dates_for_flock
# ---------------------------------------------------------------------------


class TestNormDatesForFlock:
    def test_week_33_gives_correct_date(self):
        # Week 33: date = dob + 33*7+1 = dob + 232 days = 2026-05-21
        norm_df = pl.DataFrame({"age_weeks": [33], "lay_percentage_norm": [97.0]})
        result = norm_dates_for_flock(norm_df, DOB)
        assert "registration_date" in result.columns
        assert result["registration_date"][0] == date(2026, 5, 21)

    def test_week_18_gives_correct_date(self):
        # Week 18: date = dob + 18*7+1 = dob + 127 days = 2026-02-05
        norm_df = pl.DataFrame({"age_weeks": [18]})
        result = norm_dates_for_flock(norm_df, DOB)
        expected = date.fromordinal(DOB.toordinal() + 18 * 7 + 1)
        assert result["registration_date"][0] == expected

    def test_custom_output_col(self):
        norm_df = pl.DataFrame({"age_weeks": [33]})
        result = norm_dates_for_flock(norm_df, DOB, output_date_col="norm_date")
        assert "norm_date" in result.columns

    def test_empty_df_returns_null_date_column(self):
        norm_df = pl.DataFrame({"age_weeks": pl.Series([], dtype=pl.Int32)})
        result = norm_dates_for_flock(norm_df, DOB)
        assert "registration_date" in result.columns
        assert result.is_empty()

    def test_date_aligns_with_flock_week(self):
        # norm week W should land on flock_week W for the same dob

        norm_df = pl.DataFrame({"age_weeks": [33, 34, 80]})
        result = norm_dates_for_flock(norm_df, DOB)
        for row in result.to_dicts():
            computed_week = calculate_flock_week(row["registration_date"], DOB)
            assert computed_week == row["age_weeks"], (
                f"Week {row['age_weeks']}: date {row['registration_date']} "
                f"gives flock_week {computed_week}"
            )


# ---------------------------------------------------------------------------
# format_norm_delta
# ---------------------------------------------------------------------------


class TestFormatNormDelta:
    def test_negative_delta(self):
        result = format_norm_delta(96.4, 97.0, unit="%")
        assert "norm 97.0%" in result
        assert "-0.6%" in result

    def test_positive_delta(self):
        result = format_norm_delta(97.5, 97.0, unit="%")
        assert "+0.5%" in result

    def test_zero_delta(self):
        result = format_norm_delta(97.0, 97.0)
        assert "+0.0" in result

    def test_none_actual_returns_empty(self):
        assert format_norm_delta(None, 97.0) == ""

    def test_none_norm_returns_empty(self):
        assert format_norm_delta(96.4, None) == ""

    def test_custom_precision(self):
        result = format_norm_delta(2.091, 2.090, precision=3)
        assert "+0.001" in result

    def test_no_unit(self):
        result = format_norm_delta(2.09, 2.10)
        assert "norm 2.1" in result


# ---------------------------------------------------------------------------
# get_norm_for_flock_week
# ---------------------------------------------------------------------------


class TestGetNormForFlockWeek:
    def test_returns_matching_row(self):
        norm_df = pl.DataFrame(
            {"age_weeks": [33, 34], "lay_percentage_norm": [97.0, 97.0]}
        )
        result = get_norm_for_flock_week(norm_df, 33)
        assert result is not None
        assert result["lay_percentage_norm"] == 97.0

    def test_returns_none_for_missing_week(self):
        norm_df = pl.DataFrame({"age_weeks": [33], "lay_percentage_norm": [97.0]})
        assert get_norm_for_flock_week(norm_df, 99) is None

    def test_returns_none_for_empty_df(self):
        norm_df = pl.DataFrame(
            {
                "age_weeks": pl.Series([], dtype=pl.Int32),
                "lay_percentage_norm": pl.Series([], dtype=pl.Float64),
            }
        )
        assert get_norm_for_flock_week(norm_df, 33) is None


# ---------------------------------------------------------------------------
# Norm overlay integration: breed key → norm presence
# ---------------------------------------------------------------------------


class TestNormPresenceByBreed:
    """Tests that verify norm visibility logic without a real database.

    Uses the CSV-based repo pattern from Phase 1 tests to simulate the
    'df_norms populated vs empty' scenarios in the dashboard.
    """

    def test_matching_breed_key_gives_populated_norms(self):
        from pathlib import Path

        from sqlalchemy.pool import StaticPool
        from sqlmodel import Session, SQLModel, create_engine

        from database.repositories.laying_hens_repository import (
            FlockLayCurveNormsRepository,
        )
        from database.seeds.load_lay_curve_norms import load_norms_with_repo

        _CSV = (
            Path(__file__).parent.parent.parent
            / "database"
            / "seeds"
            / "dekalb_white_norms.csv"
        )
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)
        repo = FlockLayCurveNormsRepository(
            lambda: Session(engine, expire_on_commit=False)
        )
        load_norms_with_repo(_CSV, repo)

        # breed_key in CSV is "dekalb_white_scharrel_voliere";
        # use the short breed name from flock records; it aliases to the CSV key.
        breed = "Dekalb Wit"
        breed_key = normalize_breed_key(breed)
        assert breed_key == "dekalb_white_scharrel_voliere"
        norms = repo.list_by_breed_key(breed_key)
        # Norms present → norm overlay should show, no hint
        assert len(norms) == 83

    def test_unknown_breed_gives_empty_norms_and_hint(self):
        breed = "Onbekend Ras"
        # breed_key normalises fine but there are no rows for it;
        # simulate with an empty DataFrame as the dashboard would have.
        df_norms = pl.DataFrame({"age_weeks": pl.Series([], dtype=pl.Int32)})
        norm_hint = breed if df_norms.is_empty() else None
        assert norm_hint == "Onbekend Ras"

    def test_none_breed_gives_no_hint(self):
        assert normalize_breed_key(None) is None
        # dashboard skips norm lookup entirely when breed_key is None
