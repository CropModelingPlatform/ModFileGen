"""The harvest DSSAT is given, and how many seasons come back.

A season's window runs until the day before the next season's first
operation. That is right for the window and wrong as a harvest: it left the
crop standing for the whole interval, and CROPGRO refused the fixture's
peanut after 364 days -- 300 flower cohorts, one per day of flowering, on a
crop that never matured.

``DHarvest`` is the declared duration from sowing, so it caps the harvest.
DSSAT needs no continuity: it starts the next run the day after this one
ends and simulates bare soil until that season's own sowing.
"""

import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from modfilegen.Converter.DssatConverter import dssatsuccessiveconverter as dssat

ROTATION = "ROT_MAIZE_PEANUT_3Y"


@pytest.fixture
def rotation(masterinput_db):
    connection = sqlite3.connect(masterinput_db)
    connection.row_factory = sqlite3.Row
    try:
        row = dict(
            connection.execute(
                "SELECT * FROM SimUnitList WHERE idMangt = ?", (ROTATION,)
            ).fetchone()
        )
        managements = dssat.expand_successive_managements(
            row, dssat.successive_managements(row, connection), connection
        )
        seasons = dssat.successive_season_rows(row, managements, connection)
        yield row, managements, seasons
    finally:
        connection.close()


def sowing(row, management):
    return dssat.julian_date(
        int(row["StartYear"]) + dssat.season_year_offset(management),
        int(management["sowingdate"]),
    )


# --- the cap --------------------------------------------------------------


def test_no_season_stands_longer_than_its_declared_duration(rotation):
    row, managements, seasons = rotation

    for management, season in zip(managements, seasons):
        harvest = dssat.season_harvest_date(row, season, management)
        duration = (harvest - sowing(row, management)).days
        assert duration <= int(management["DHarvest"])


def test_the_peanut_season_is_capped(rotation):
    """364 days of window become 200 of declared duration."""
    row, managements, seasons = rotation
    management, season = managements[1], seasons[1]

    window = (dssat.row_end_date(season) - sowing(row, management)).days
    harvest = dssat.season_harvest_date(row, season, management)

    assert window == 364
    assert (harvest - sowing(row, management)).days == 200


def test_a_window_shorter_than_the_duration_is_kept(rotation):
    """The cap is a ceiling, not a target: season 3's window is already
    exactly the declared duration, so nothing moves."""
    row, managements, seasons = rotation
    management, season = managements[2], seasons[2]

    assert dssat.season_harvest_date(row, season, management) == dssat.row_end_date(
        season
    )


def test_no_declared_duration_leaves_the_window_alone(rotation):
    row, managements, seasons = rotation

    for value in (0, None, "", "0", "not a number"):
        management = dict(managements[0])
        management["DHarvest"] = value
        assert dssat.season_harvest_date(
            row, seasons[0], management
        ) == dssat.row_end_date(seasons[0])


def test_the_season_windows_themselves_do_not_move(rotation):
    """Only HDATE is capped. The boundary rule -- a season ends the day
    before the next season's first operation -- is untouched."""
    _, _, seasons = rotation

    for first, second in zip(seasons, seasons[1:]):
        assert dssat.row_start_date(second) == dssat.row_end_date(first) + timedelta(
            days=1
        )


# --- and only the declared seasons come back ------------------------------


def summary_file(directory, runs):
    """A Summary.OUT with one line per run: ``(R#, planting as YYYYDDD)``.

    Thirteen identifier columns then the variables, which is where the
    reader splits; ``R#`` is the third and names the rotation DSSAT was
    running, ``PDAT`` the day it sowed.
    """
    names = (
        "RUNNO TRNO R# O# P# CR MODEL EXNAME TNAM FNAM WSTA WYEAR SOIL_ID"
        " PDAT HWAM"
    )
    lines = ["*SUMMARY\n", "\n", "!IDENTIFIERS\n", f"@{names}\n"]
    for run, (number, planting) in enumerate(runs, start=1):
        lines.append(
            f"{run} 1 {number} 0 1 MZ MZCER048 ITSA1301 name fnam wsta 2000"
            f" soil {planting} {1000 + run}\n"
        )
    summary = Path(directory) / "Summary.OUT"
    summary.write_text("".join(lines))
    return summary


def fake_rotations(count, end=(2002, 350)):
    from types import SimpleNamespace

    return [
        SimpleNamespace(
            index=index,
            row={
                "idsim": "sim",
                "idPoint": "p",
                "StartYear": 2000,
                "EndYear": end[0],
                "EndDay": end[1],
            },
            management={"SeasonOrder": index, "PlantOrder": 1},
            crop="MZ",
        )
        for index in range(1, count + 1)
    ]


def test_a_cycle_sown_past_the_simulation_is_dropped(tmp_path):
    """The leak this closed. FERT_MIN_ORG declares one season ending in 2001,
    and DSSAT cycled its treatment list into 2002 because NYERS leaves slack;
    that second sowing became a season nobody asked for.
    """
    summary = summary_file(tmp_path, [(1, 2001150), (1, 2002150)])

    frame = dssat.transform_sequence(
        summary, fake_rotations(1, end=(2001, 350))
    )

    assert len(frame) == 1


def test_a_cycle_sown_inside_the_simulation_is_kept(tmp_path):
    """A one-season management is meant to repeat over the period, so a
    cycle that sows within the declared window is a real season."""
    summary = summary_file(tmp_path, [(1, 2001150), (1, 2002150)])

    frame = dssat.transform_sequence(
        summary, fake_rotations(1, end=(2002, 350))
    )

    assert len(frame) == 2
    assert list(frame["SeasonOrder"]) == [1, 2]


def test_a_cycled_rotation_is_read_once_per_season(tmp_path):
    """Three declared seasons, and a fourth run from the engine's own cycle,
    which carries rotation number 1 again and is already deduplicated."""
    summary = summary_file(
        tmp_path, [(1, 2000150), (2, 2001150), (3, 2002150), (1, 2003150)]
    )

    frame = dssat.transform_sequence(summary, fake_rotations(3))

    assert len(frame) == 3
    assert list(frame["SeasonOrder"]) == [1, 2, 3]


def test_a_shorter_run_than_declared_is_not_padded(tmp_path):
    """Fewer runs than seasons is a failure to report, not one to invent."""
    summary = summary_file(tmp_path, [(1, 2000150), (2, 2001150)])

    frame = dssat.transform_sequence(summary, fake_rotations(3))

    assert len(frame) == 2
