import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from modfilegen.Converter.SticsV11Converter import sticssuccessiveconverter as converter
from modfilegen.Converter.SticsV11Converter.sticsconverter import (
    build_balanced_simulation_chunks,
    fetch_data_from_sqlite,
    get_simulation_weights,
    partition_simulations,
)

ROTATION_IDSIM = "5.925_6.025_2000_ROT_MAIZE_PEANUT_3Y_2"


def pattern_connection():
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE CropManagement (
            idMangt TEXT,
            SeasonOrder INTEGER,
            PlantOrder INTEGER,
            SowingYearOffset INTEGER,
            sowingdate INTEGER,
            DHarvest INTEGER,
            Idcultivar TEXT
        );
        CREATE TABLE ListCultivars (IdCultivar TEXT, SpeciesName TEXT);
        INSERT INTO ListCultivars VALUES ('maize', 'maize');
        INSERT INTO ListCultivars VALUES ('bean', 'bean');
        INSERT INTO ListCultivars VALUES ('legume', 'legume');
        INSERT INTO CropManagement VALUES ('rotation', 1, 1, 0, 100, 80, 'maize');
        INSERT INTO CropManagement VALUES ('rotation', 1, 2, 0, 100, 90, 'bean');
        INSERT INTO CropManagement VALUES ('rotation', 2, 1, 0, 250, 70, 'legume');
        """
    )
    return connection


def test_management_pattern_repeats_with_seasons_and_plant_orders():
    simulation = {
        "idMangt": "rotation",
        "StartYear": 2000,
        "StartDay": 1,
        "EndYear": 2002,
        "EndDay": 365,
    }
    with pattern_connection() as connection:
        seasons = converter.fetch_rotation_seasons(connection, simulation)

    assert [season["SeasonOrder"] for season in seasons] == [1, 2, 3, 4, 5, 6]
    assert [season["ManagementSeasonOrder"] for season in seasons] == [1, 2, 1, 2, 1, 2]
    assert [season["SeasonYearOffset"] for season in seasons] == [0, 0, 1, 1, 2, 2]
    assert [plant["PlantOrder"] for plant in seasons[0]["Plants"]] == [1, 2]
    assert [plant["ManagementPlantOrder"] for plant in seasons[0]["Plants"]] == [1, 2]
    assert seasons[0]["StartDate"] == converter.julian_date(2000, 1)
    assert seasons[0]["EndDate"] == converter.julian_date(2000, 249)
    assert seasons[1]["StartDate"] == converter.julian_date(2000, 250)
    assert seasons[-1]["EndDate"] == converter.julian_date(2002, 365)




def test_collect_reports_preserves_associated_plant_identity(tmp_path, monkeypatch):
    season_key = "rotation__season_001"
    for role in ("P", "A"):
        (tmp_path / f"mod_rapport{role}_{season_key}.sti").write_text("row\n")

    calls = []

    def fake_summary(path, coordinates, idsim, plant_role, preserve_raw=False):
        calls.append((plant_role, preserve_raw))
        return converter.pd.DataFrame(
            [{"Model": "Stics", "Idsim": idsim, "Texte": plant_role}]
        )

    monkeypatch.setattr(converter, "create_df_summary", fake_summary)
    frames = converter.collect_reports(
        {"idsim": "rotation"},
        {"IsMixedCrop": True, "SeasonOrder": 1},
        season_key,
        tmp_path,
        object(),
        "header",
    )
    result = converter.pd.concat(frames, ignore_index=True)

    assert calls == [("P", True), ("A", True)]
    assert result[["Texte", "PlantOrder"]].to_dict("records") == [
        {"Texte": "P", "PlantOrder": 1},
        {"Texte": "A", "PlantOrder": 2},
    ]

def test_first_management_operation_sets_next_season_boundary():
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE CropManagement (
            idMangt TEXT,
            SeasonOrder INTEGER,
            PlantOrder INTEGER,
            SeasonYearOffset INTEGER,
            sowingdate INTEGER,
            Idcultivar TEXT,
            SoilTillPolicyCode TEXT
        );
        CREATE TABLE ListCultivars (IdCultivar TEXT, SpeciesName TEXT);
        CREATE TABLE SoilTillageOperations (
            SoilTillPolicyCode TEXT, DSTill INTEGER
        );
        INSERT INTO ListCultivars VALUES ('maize', 'maize');
        INSERT INTO CropManagement
        VALUES ('rotation', 1, 1, 0, 100, 'maize', 'till1');
        INSERT INTO CropManagement
        VALUES ('rotation', 2, 1, 1, 150, 'maize', 'till2');
        INSERT INTO SoilTillageOperations VALUES ('till1', -5);
        INSERT INTO SoilTillageOperations VALUES ('till2', -10);
        """
    )
    simulation = {
        "idMangt": "rotation",
        "StartYear": 2000,
        "StartDay": 1,
        "EndYear": 2001,
        "EndDay": 365,
    }
    try:
        seasons = converter.fetch_rotation_seasons(connection, simulation)
    finally:
        connection.close()

    second_operation = converter.julian_date(2001, 150) - converter.timedelta(days=10)
    assert seasons[0]["EndDate"] == second_operation - converter.timedelta(days=1)
    assert seasons[1]["StartDate"] == second_operation
    assert seasons[0]["EndDate"] != (
        converter.julian_date(2000, 100) + converter.timedelta(days=999)
    )

def test_single_offset_one_pattern_repeats_annually_from_following_year():
    simulation = {
        "idMangt": "annual",
        "StartYear": 1992,
        "StartDay": 305,
        "EndYear": 1995,
        "EndDay": 181,
    }
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE CropManagement (
            idMangt TEXT,
            SeasonOrder INTEGER,
            PlantOrder INTEGER,
            SowingYearOffset INTEGER,
            sowingdate INTEGER,
            DHarvest INTEGER,
            Idcultivar TEXT
        );
        CREATE TABLE ListCultivars (IdCultivar TEXT, SpeciesName TEXT);
        INSERT INTO ListCultivars VALUES ('wheat', 'wheat');
        INSERT INTO CropManagement
        VALUES ('annual', 1, 1, 1, 15, 180, 'wheat');
        """
    )
    try:
        seasons = converter.fetch_rotation_seasons(connection, simulation)
    finally:
        connection.close()

    assert [plant["SowingDate"] for season in seasons for plant in season["Plants"]] == [
        converter.julian_date(1993, 15),
        converter.julian_date(1994, 15),
        converter.julian_date(1995, 15),
    ]
    assert [season["EndDate"] for season in seasons] == [
        converter.julian_date(1994, 14),
        converter.julian_date(1995, 14),
        converter.julian_date(1995, 181),
    ]


# Tests on the text MasterInput fixture: three Mgt1M0_135 standard
# simulations, the FERT_MIN_ORG standard simulation and one three-season
# rotation (ROT_MAIZE_PEANUT_3Y).


def rotation_example(masterinput_db):
    connection = sqlite3.connect(masterinput_db)
    connection.row_factory = sqlite3.Row
    simulation = dict(
        connection.execute(
            "SELECT * FROM SimUnitList WHERE idsim = ?", (ROTATION_IDSIM,)
        ).fetchone()
    )
    return connection, simulation


def test_all_simulations_are_balanced_by_number_of_seasons(masterinput_db):
    simulations = fetch_data_from_sqlite(masterinput_db)
    weights = get_simulation_weights(masterinput_db, simulations)

    chunks = build_balanced_simulation_chunks(simulations, weights, 2)
    loads = [sum(weights[str(row["idsim"])] for row in chunk) for chunk in chunks]

    assert len(simulations) == 5
    assert loads == [4, 3]
    assert [[weights[str(row["idsim"])] for row in chunk] for chunk in chunks] == [
        [3, 1],
        [1, 1, 1],
    ]


@pytest.mark.parametrize(
    ("row", "expected_fclim1", "expected_fclim2", "expected_nbans"),
    [
        (
            {"StartYear": 2000, "StartDay": 120, "EndYear": 2000,
             "EndDay": 350, "idPoint": "5.925_6.025"},
            "cli5.925_6.025j.2000",
            "cli5.925_6.025j.2000",
            "1",
        ),
        (
            {"StartYear": 2000, "StartDay": 351, "EndYear": 2001,
             "EndDay": 350, "idPoint": "5.925_6.025"},
            "cli5.925_6.025j.2000",
            "cli5.925_6.025j.2001",
            "2",
        ),
    ],
)
def test_climate_files_follow_season_start_and_end_years(
    tmp_path, row, expected_fclim1, expected_fclim2, expected_nbans
):
    usm = Path(tmp_path) / "new_travail.usm"
    usm.write_text(
        ":datedebut\n0\n:datefin\n0\n:fclim1\nunset\n:fclim2\nunset\n"
        ":nbans\n0\n:culturean\n0\n"
    )

    converter.adapt_usm_calendar(str(tmp_path), row)

    values = usm.read_text().splitlines()
    parameters = {
        values[index][1:]: values[index + 1] for index in range(0, len(values), 2)
    }
    assert parameters["fclim1"] == expected_fclim1
    assert parameters["fclim2"] == expected_fclim2
    assert parameters["nbans"] == expected_nbans


def test_single_entry_point_partitions_standard_and_successive_managements(
    masterinput_db,
):
    simulations = fetch_data_from_sqlite(masterinput_db)

    standard, successive = partition_simulations(masterinput_db, simulations)

    assert len(standard) == 4
    assert {row["idMangt"] for row in standard} == {"Mgt1M0_135", "FERT_MIN_ORG"}
    assert [row["idsim"] for row in successive] == [ROTATION_IDSIM]


def test_three_year_rotation_is_expanded_from_one_simulation(masterinput_db):
    connection, simulation = rotation_example(masterinput_db)
    try:
        seasons = converter.fetch_rotation_seasons(connection, simulation)
    finally:
        connection.close()

    assert [season["SeasonOrder"] for season in seasons] == [1, 2, 3]
    assert [season["Plants"][0]["Idcultivar"] for season in seasons] == [
        "testcult", "testcult2", "testcult",
    ]
    assert [season["Plants"][0]["SowingDate"].year for season in seasons] == [
        2000, 2001, 2002,
    ]


def test_each_season_ends_the_day_before_the_next_season_starts(masterinput_db):
    connection, simulation = rotation_example(masterinput_db)
    try:
        seasons = converter.fetch_rotation_seasons(connection, simulation)
    finally:
        connection.close()

    for previous, following in zip(seasons, seasons[1:]):
        assert following["StartDate"] == previous["EndDate"] + timedelta(days=1)
    # Season 2 starts with its irrigation, 10 days before sowing; each season
    # therefore also covers the fallow after its own harvest.
    assert seasons[1]["StartDate"] == seasons[1]["Plants"][0]["SowingDate"] - timedelta(days=10)

    rows = [converter.build_season_row(simulation, season) for season in seasons]
    assert [(row["StartYear"], row["EndYear"]) for row in rows] == [
        (2000, 2001), (2001, 2002), (2002, 2002),
    ]
