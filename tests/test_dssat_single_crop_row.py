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


# --- reading the layer's value or the soil's -----------------------------

#: `writeBlockInitialConditionData` joins Soil, SoilLayers and
#: InitialConditions and expands all three with `*`. Soil and SoilLayers
#: share `bd`, `Wwp`, `Wfc`, `cf`, `OrganicC`, `pH`, `Ssat` and `Ssks` by
#: design, not by accident: `Soil` describes the whole soil and is the
#: fallback for a missing layer value, as `docs/source/database.rst` says.
#: The query aliases them so both are reachable -- `Soil.Wwp` is the
#: fallback, `SoilLayers.Wwp` the layer -- and that pairing is what these
#: tests hold, because losing an alias would silently read the whole soil
#: where the layer is meant, and nothing would fail.
ALIASED_PAIRS = (
    ("Soil.Wwp", "SoilLayers.Wwp"),
    ("Soil.Wfc", "SoilLayers.Wfc"),
    ("Soil.cf", "SoilLayers.cf"),
)

INITIAL_CONDITIONS_QUERY = """
    SELECT DISTINCT Soil.IdSoil AS 'Soil.IdSoil',
        Soil.Wwp AS 'Soil.Wwp', Soil.Wfc AS 'Soil.Wfc',
        Soil.cf AS 'Soil.cf', Soil.bd as 'soil.bd', Soil.*,
        SoilLayers.Wwp AS 'SoilLayers.Wwp', SoilLayers.Wfc AS 'SoilLayers.Wfc',
        SoilLayers.cf AS 'SoilLayers.cf', SoilLayers.*,
        InitialConditions.* FROM InitialConditions INNER JOIN
        ((Soil INNER JOIN SimUnitList ON Lower(Soil.IdSoil) = Lower(SimUnitList.idsoil))
         LEFT JOIN SoilLayers ON Lower(Soil.IdSoil) = Lower(SoilLayers.idsoil))
        ON InitialConditions.idIni = SimUnitList.idIni
        WHERE IdSim = ? ORDER BY NumLayer
"""


def initial_conditions_frame(masterinput_copy):
    import pandas as pd

    link = sqlite3.connect(str(masterinput_copy))
    try:
        return pd.read_sql_query(
            INITIAL_CONDITIONS_QUERY, link,
            params=("5.925_6.025_2001_FERT_MIN_ORG_2",),
        )
    finally:
        link.close()


@pytest.mark.parametrize("fallback,layer", ALIASED_PAIRS)
def test_both_the_layer_value_and_its_fallback_are_reachable(
    fallback, layer, masterinput_copy
):
    """What the aliases are for. Without them the bare name resolves to
    Soil's column, and the layer's would be read as the whole soil's."""
    frame = initial_conditions_frame(masterinput_copy)

    assert fallback in frame.columns
    assert layer in frame.columns


def test_the_soil_identifier_keeps_its_alias(masterinput_copy):
    """`IdSoil` is in Soil and `idsoil` in SoilLayers, matched without case,
    so the one the writer wants is spelled out."""
    frame = initial_conditions_frame(masterinput_copy)

    assert "Soil.IdSoil" in frame.columns


def test_a_column_of_this_frame_is_a_series_not_a_frame(masterinput_copy):
    """`frame[name]` returns a DataFrame when the name is duplicated, and
    then `.values[i]` is a whole row and `pd.notna` an array -- which is how
    the residues column raised. pandas suffixes the duplicates instead, so
    every lookup here yields a Series and `.values[i]` a scalar.
    """
    import pandas as pd

    frame = initial_conditions_frame(masterinput_copy)

    for name in ("SoilOption", "SoilTotalDepth", "Ldown", "Ninit",
                 "Soil.Wwp", "SoilLayers.Wwp"):
        column = frame[name]
        assert isinstance(column, pd.Series), name
        assert column.values.ndim == 1, name
