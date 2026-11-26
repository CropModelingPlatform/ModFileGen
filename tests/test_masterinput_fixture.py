import csv
import sqlite3

from build_fixtures import MASTERINPUT_SOURCES, NULL_MARKER, is_output_table


def _tables(connection):
    return {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def test_fixture_contains_every_source_table(masterinput_db):
    expected = {path.stem for path in MASTERINPUT_SOURCES.glob("*.csv")}
    with sqlite3.connect(masterinput_db) as connection:
        assert _tables(connection) == expected
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_fixture_row_counts_match_csv(masterinput_db):
    with sqlite3.connect(masterinput_db) as connection:
        for path in MASTERINPUT_SOURCES.glob("*.csv"):
            with open(path, encoding="utf-8", newline="") as handle:
                rows = sum(1 for _ in csv.reader(handle)) - 1
            count = connection.execute(f'SELECT COUNT(*) FROM "{path.stem}"').fetchone()[0]
            assert count == rows, path.stem


def test_fixture_has_no_output_tables(masterinput_db):
    with sqlite3.connect(masterinput_db) as connection:
        assert not [name for name in _tables(connection) if is_output_table(name)]


def test_null_marker_and_empty_string_are_distinct(masterinput_db):
    with sqlite3.connect(masterinput_db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM Coordinates WHERE codeSWstation = ''"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM ListCultOption WHERE DSCROP = ?", (NULL_MARKER,)
        ).fetchone()[0] == 0


def test_copy_is_isolated(masterinput_db, masterinput_copy):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute("DELETE FROM SimUnitList")
    with sqlite3.connect(masterinput_db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM SimUnitList").fetchone()[0] > 0


def test_celsius_v32_template_keeps_references_and_default_rows(celsius_v32_template_db):
    from build_fixtures import CELSIUS_V32_DEFAULT_ROW_TABLES, CELSIUS_V32_EMPTY_TABLES

    with sqlite3.connect(celsius_v32_template_db) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        names = {name.lower(): name for name in _tables(connection)}
        for table in CELSIUS_V32_EMPTY_TABLES:
            assert connection.execute(f'SELECT COUNT(*) FROM "{names[table]}"').fetchone()[0] == 0
        for table in CELSIUS_V32_DEFAULT_ROW_TABLES:
            assert connection.execute(f'SELECT COUNT(*) FROM "{names[table]}"').fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM Cultivars").fetchone()[0] > 0


def test_masterinput_cultivars_resolve_in_celsius_v32_template(
    masterinput_db, celsius_v32_template_db
):
    with sqlite3.connect(masterinput_db) as connection:
        codes = {
            row[0] for row in connection.execute(
                "SELECT DISTINCT l.IdcultivarCelsius FROM CropManagement c "
                "JOIN ListCultivars l ON l.IdCultivar = c.Idcultivar"
            )
        }
    with sqlite3.connect(celsius_v32_template_db) as connection:
        known = {str(row[0]) for row in connection.execute("SELECT IdCultivar FROM Cultivars")}
    assert codes and codes <= known


def test_modelsdictionary_holds_only_the_variables_table(modelsdictionary_db):
    with sqlite3.connect(modelsdictionary_db) as connection:
        assert _tables(connection) == {"Variables"}
        models = {
            row[0] for row in connection.execute("SELECT DISTINCT model FROM Variables")
        }
    assert {"master", "stics", "sticsv11", "dssat", "celsius"} <= models


def test_the_fixture_carries_one_override_per_model(masterinput_db):
    """The fixture exercises the generic override route for both models.

    `(idMangt, SeasonOrder, PlantOrder)` is per crop-season, so the rotation
    can give its peanut season a MEPHO of its own -- DSSAT's photosynthesis
    method is R for a CERES maize and C or L for a CROPGRO legume, and the
    two cannot share one SIMULATION CONTROLS block. Without a row in the
    fixture, that path is only ever reached by hand.
    """
    with sqlite3.connect(masterinput_db) as connection:
        overrides = {
            (row[0], row[1], row[2], row[3], row[4]): row[5]
            for row in connection.execute(
                "SELECT Model, idMangt, SeasonOrder, TargetTable, Parameter,"
                " Value FROM CropManagementParameterOverrides"
            )
        }

    assert overrides[
        ("sticsv11", "ROT_MAIZE_PEANUT_3Y", 3, "fictec1", "codecalirrig")
    ] == "1"
    assert overrides[
        ("dssat", "ROT_MAIZE_PEANUT_3Y", 2, "dssat_x_simulation_method", "MEPHO")
    ] == "L"


def test_the_overridden_season_is_the_one_that_grows_the_legume(masterinput_db):
    """A MEPHO of L on a maize season would be wrong, not just useless."""
    with sqlite3.connect(masterinput_db) as connection:
        season, = connection.execute(
            "SELECT SeasonOrder FROM CropManagementParameterOverrides"
            " WHERE lower(Model) = 'dssat' AND Parameter = 'MEPHO'"
        ).fetchone()
        species, = connection.execute(
            "SELECT l.SpeciesName FROM CropManagement c"
            " JOIN ListCultivars l ON l.IdCultivar = c.Idcultivar"
            " WHERE c.idMangt = 'ROT_MAIZE_PEANUT_3Y' AND c.SeasonOrder = ?",
            (season,),
        ).fetchone()

    assert species == "peanut"
