"""The dated irrigations DSSAT is given.

This block used to be written from the ModelsDictionary alone: one line
carrying IDLAPL, IRRCOD and IIRV, which are template defaults. A policy
declaring three irrigations of 20, 30 and 30 mm came out as a single one of
27.9 mm, on 10177 -- a date in no year of the simulation. Nothing said so;
the file looked plausible.
"""

import sqlite3

import pytest

from modfilegen.Converter.DssatConverter.dssatxconverter import (
    format_dssat_yyddd,
    writeBlockIrrigationWaterData,
)

TABLE = "dssat_x_irrigation_water_data"


@pytest.fixture
def dictionary():
    """The template defaults this block used to write on its own."""
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE Variables (model TEXT, [Table] TEXT, Champ TEXT,"
        " Default_Value_Datamill TEXT, defaultValueOtherSource TEXT)"
    )
    connection.executemany(
        "INSERT INTO Variables VALUES ('dssat', ?, ?, ?, NULL)",
        [
            (TABLE, "LNIR", "1"),
            (TABLE, "IDLAPL", "10177"),
            (TABLE, "IRRCOD", "IR002"),
            (TABLE, "IIRV", "27.9"),
        ],
    )
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def master(masterinput_copy):
    connection = sqlite3.connect(str(masterinput_copy))
    # What configure_season_connection exposes to the legacy writers: one
    # season's management row, and SimUnitList recast on that season's own
    # window. Without the recast the year would be the rotation's first.
    connection.execute(
        "DELETE FROM CropManagement WHERE NOT"
        " (idMangt = 'ROT_MAIZE_PEANUT_3Y' AND SeasonOrder = 2)"
    )
    connection.execute(
        "UPDATE SimUnitList SET StartYear = 2001, StartDay = 140,"
        " EndYear = 2002, EndDay = 149"
        " WHERE idMangt = 'ROT_MAIZE_PEANUT_3Y'"
    )
    connection.commit()
    try:
        yield connection
    finally:
        connection.close()


def lines(block):
    return [
        line for line in block.splitlines() if line.strip() and not line.startswith("@")
    ]


def test_every_declared_irrigation_is_written(dictionary, master):
    """IRR_ROT_TEST declares three: -10 days 20 mm, +20 days 30 mm, +50 30 mm."""
    declared = master.execute(
        "SELECT COUNT(*) FROM IrrigationFOperations"
        " WHERE IrrigationPolicyCode = 'IRR_ROT_TEST'"
    ).fetchone()[0]

    block = writeBlockIrrigationWaterData(
        TABLE, dictionary, "5.925_6.025_2000_ROT_MAIZE_PEANUT_3Y_2", master, "R"
    )

    assert declared == 3
    assert len(lines(block)) == 3


def test_the_declared_amounts_are_used(dictionary, master):
    block = writeBlockIrrigationWaterData(
        TABLE, dictionary, "5.925_6.025_2000_ROT_MAIZE_PEANUT_3Y_2", master, "R"
    )

    amounts = [line.split()[-1] for line in lines(block)]
    assert amounts == ["20.0", "30.0", "30.0"]
    assert "27.9" not in block


def test_a_date_is_the_sowing_plus_the_offset(dictionary, master):
    """Sowing on day 150 of 2001, so -10 is 01140 and +50 is 01200."""
    block = writeBlockIrrigationWaterData(
        TABLE, dictionary, "5.925_6.025_2000_ROT_MAIZE_PEANUT_3Y_2", master, "R"
    )

    dates = [line.split()[1] for line in lines(block)]
    assert dates == ["01140", "01170", "01200"]
    assert "10177" not in block


def test_days_after_planting_are_written_as_offsets(dictionary, master):
    """What the simulation options ask for when IIRRI is 'D'."""
    block = writeBlockIrrigationWaterData(
        TABLE, dictionary, "5.925_6.025_2000_ROT_MAIZE_PEANUT_3Y_2", master, "D"
    )

    assert [line.split()[1] for line in lines(block)] == ["-10", "20", "50"]


def test_without_a_database_the_defaults_still_come_out(dictionary):
    """Every caller used to get this, and one may still not pass a database."""
    block = writeBlockIrrigationWaterData(TABLE, dictionary)

    assert len(lines(block)) == 1
    assert "27.9" in block


def test_a_simulation_without_irrigation_writes_no_line(dictionary, master):
    block = writeBlockIrrigationWaterData(
        TABLE, dictionary, "5.925_6.025_2001_FERT_MIN_ORG_2", master, "R"
    )

    assert lines(block) == []


# --- dates before the first of January ------------------------------------


def test_an_operation_before_new_year_rolls_back():
    """Operations before sowing are negative, so a crop sown on day 5 has
    them in the previous year. Only the overflow past December was handled,
    and the other direction gave a day of 0 or less."""
    assert format_dssat_yyddd(2001, -5) == "00361"
    assert format_dssat_yyddd(2001, 0) == "00366"  # 2000 is a leap year
    assert format_dssat_yyddd(2002, 0) == "01365"


def test_an_operation_past_december_still_rolls_forward():
    assert format_dssat_yyddd(2000, 367) == "01001"
    assert format_dssat_yyddd(2001, 150) == "01150"
