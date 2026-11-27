"""Every X-file writer sees exactly one CropManagement row.

Thirty-six `.values[0]` in `dssatxconverter` read a frame joined to
CropManagement and take the first row. They are correct only while that
frame holds one row, and nothing in those functions enforces it: the
guarantee comes from elsewhere, and from guards added for other reasons.

* standard mode refuses a management with several plants in a season or
  several seasons, and the guard sits in the cultivar converter, which runs
  before the X writer;
* successive mode hands the writers a database restricted to one
  `(idMangt, SeasonOrder, PlantOrder)`.

Relax either and those thirty-six silently pick a row at random again --
which is the shape of the defect that made no management applying organic
matter twice convertible. Hence these tests.
"""

import re
import sqlite3
from pathlib import Path

import pytest

from modfilegen.Converter.DssatConverter import (
    applicability,
    dssatsuccessiveconverter as successive,
)


def crop_rows(connection, idMangt):
    return connection.execute(
        "SELECT COUNT(*) FROM CropManagement WHERE idMangt = ?", (idMangt,)
    ).fetchone()[0]


@pytest.fixture
def connection(masterinput_copy):
    link = sqlite3.connect(str(masterinput_copy))
    link.row_factory = sqlite3.Row
    try:
        yield link
    finally:
        link.close()


# --- standard mode --------------------------------------------------------


def test_standard_mode_sees_one_row_or_refuses_the_management(connection):
    """The invariant, stated over every management in the fixture."""
    managements = [
        row[0]
        for row in connection.execute("SELECT DISTINCT idMangt FROM CropManagement")
    ]
    assert managements, "the fixture must declare managements"

    for idMangt in managements:
        rows = crop_rows(connection, idMangt)
        if rows == 1:
            applicability.check(idMangt, connection, "standard")
            continue
        with pytest.raises(applicability.NotApplicable):
            applicability.check(idMangt, connection, "standard")


def test_the_guard_runs_before_the_x_writer():
    """What makes the standard guarantee hold in practice: the guard lives in
    the cultivar converter, and process_chunk calls it first."""
    source = (
        Path(__file__).parent.parent
        / "src/modfilegen/Converter/DssatConverter/dssatconverter.py"
    ).read_text(encoding="utf-8")
    cultivar = source.index("cultivarconverter.export(")
    writer = source.index("xconverter.export(")

    assert cultivar < writer, (
        "the applicability guard must run before the X file is written"
    )


# --- successive mode ------------------------------------------------------


def test_successive_mode_exposes_one_season_at_a_time(connection):
    """A rotation has three seasons; the writers must see one."""
    simulation = dict(
        connection.execute(
            "SELECT * FROM SimUnitList WHERE idMangt = 'ROT_MAIZE_PEANUT_3Y'"
        ).fetchone()
    )
    assert crop_rows(connection, "ROT_MAIZE_PEANUT_3Y") == 3

    season = successive.successive_group_connection(connection)
    try:
        for order in (1, 2, 3):
            successive.configure_season_connection(
                season, simulation,
                {"idMangt": "ROT_MAIZE_PEANUT_3Y", "SeasonOrder": order,
                 "PlantOrder": 1},
            )
            assert crop_rows(season, "ROT_MAIZE_PEANUT_3Y") == 1
            kept, = season.execute(
                "SELECT SeasonOrder FROM CropManagement"
            ).fetchone()
            assert kept == order
    finally:
        season.close()


def test_the_untouched_source_keeps_every_season(connection):
    """The restriction is a view for the legacy writers, not a deletion."""
    simulation = dict(
        connection.execute(
            "SELECT * FROM SimUnitList WHERE idMangt = 'ROT_MAIZE_PEANUT_3Y'"
        ).fetchone()
    )

    season = successive.successive_group_connection(connection)
    try:
        successive.configure_season_connection(
            season, simulation,
            {"idMangt": "ROT_MAIZE_PEANUT_3Y", "SeasonOrder": 2, "PlantOrder": 1},
        )
    finally:
        season.close()

    assert crop_rows(connection, "ROT_MAIZE_PEANUT_3Y") == 3


# --- and the shape that started this --------------------------------------


def test_no_converter_asks_numpy_for_the_truth_of_a_column():
    """`if frame["column"].values:` raises with more than one row. It worked
    by accident with a single residue and broke with two."""
    root = Path(__file__).parent.parent / "src/modfilegen/Converter"
    pattern = re.compile(r"if\s+\w+\[[^\]]+\]\.values\s*:")

    offenders = []
    for path in sorted(root.rglob("*.py")):
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if pattern.search(line) and not line.strip().startswith("#"):
                offenders.append(f"{path.name}:{number} {line.strip()}")

    assert not offenders, (
        "a whole column's truth is ambiguous; test the row being written:\n"
        + "\n".join(offenders)
    )
