"""One season ends the day before the next season's first operation.

Not the day before its sowing: a season owns the operations that precede
its own sowing. The fixture's rotation irrigates ten days before the
peanut goes in, so season 1 closes eleven days before that sowing -- and
the irrigation falls where it belongs, on the crop it is meant for.

STICS v11 and DSSAT both state the rule in the same shape, and each has a
test of its own. What neither of them pins is that the two agree, which is
the invariant the whole comparison between models rests on: the same
database must describe the same calendar to both.
"""

import sqlite3
from datetime import timedelta

import pytest

from modfilegen.Converter.DssatConverter import dssatsuccessiveconverter as dssat
from modfilegen.Converter.SticsV11Converter import sticssuccessiveconverter as stics

ROTATION = "ROT_MAIZE_PEANUT_3Y"


@pytest.fixture
def simulation(masterinput_db):
    connection = sqlite3.connect(masterinput_db)
    connection.row_factory = sqlite3.Row
    try:
        yield dict(
            connection.execute(
                "SELECT * FROM SimUnitList WHERE idMangt = ?", (ROTATION,)
            ).fetchone()
        ), connection
    finally:
        connection.close()


def dssat_windows(row, connection):
    managements = dssat.successive_managements(row, connection)
    seasons = dssat.successive_season_rows(row, managements, connection)
    return [
        (dssat.row_start_date(season), dssat.row_end_date(season))
        for season in seasons
    ], [
        dssat.management_first_operation_date(management, row, connection)
        for management in managements
    ]


def stics_windows(row, connection):
    seasons = stics.fetch_rotation_seasons(connection, row)
    return (
        [(season["StartDate"], season["EndDate"]) for season in seasons],
        [season["FirstOperationDate"] for season in seasons],
    )


# --- the rule, for each model --------------------------------------------


@pytest.mark.parametrize("windows_of", [dssat_windows, stics_windows])
def test_a_season_ends_the_day_before_the_next_first_operation(
    windows_of, simulation
):
    row, connection = simulation

    windows, first_operations = windows_of(row, connection)

    for index in range(len(windows) - 1):
        _, end = windows[index]
        assert end + timedelta(days=1) == first_operations[index + 1], (
            f"season {index + 1} must end the day before season "
            f"{index + 2}'s first operation"
        )


@pytest.mark.parametrize("windows_of", [dssat_windows, stics_windows])
def test_the_last_season_ends_with_the_simulation(windows_of, simulation):
    row, connection = simulation

    windows, _ = windows_of(row, connection)

    assert windows[-1][1] == dssat.row_end_date(row)


@pytest.mark.parametrize("windows_of", [dssat_windows, stics_windows])
def test_the_first_season_starts_with_the_simulation(windows_of, simulation):
    """Its own first operation may come later; the simulation owns the lead."""
    row, connection = simulation

    windows, _ = windows_of(row, connection)

    assert windows[0][0] == dssat.row_start_date(row)


@pytest.mark.parametrize("windows_of", [dssat_windows, stics_windows])
def test_the_windows_are_contiguous_and_cover_everything(windows_of, simulation):
    """No day simulated twice, none left out."""
    row, connection = simulation

    windows, _ = windows_of(row, connection)

    for (_, end), (start, _) in zip(windows, windows[1:]):
        assert start == end + timedelta(days=1)


# --- and the two models agree -------------------------------------------


def test_both_models_read_the_same_calendar(simulation):
    row, connection = simulation

    dssat_seasons, _ = dssat_windows(row, connection)
    stics_seasons, _ = stics_windows(row, connection)

    assert dssat_seasons == stics_seasons


def test_the_boundary_is_not_the_sowing_date(simulation):
    """The distinction this file exists for.

    The rotation's season 2 irrigates ten days before sowing, so the
    boundary is eleven days before it. If someone moves the boundary to the
    sowing, that irrigation lands in season 1 -- on the previous crop's
    bare-soil phase instead of the peanut it was written for.
    """
    row, connection = simulation

    windows, first_operations = dssat_windows(row, connection)
    managements = dssat.successive_managements(row, connection)

    sowing_of_season_2 = dssat.julian_date(
        int(row["StartYear"]) + dssat.season_year_offset(managements[1]),
        int(managements[1]["sowingdate"]),
    )
    end_of_season_1 = windows[0][1]

    assert first_operations[1] < sowing_of_season_2
    assert end_of_season_1 == first_operations[1] - timedelta(days=1)
    assert (sowing_of_season_2 - end_of_season_1).days == 11
