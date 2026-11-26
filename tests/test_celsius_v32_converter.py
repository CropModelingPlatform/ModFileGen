import shutil
from datetime import date
import sqlite3

import pytest

from modfilegen.Converter.CelsiusV32Converter import core
from modfilegen.Converter.CelsiusV32Converter.core import convert_database


TARGET_SCHEMA = """
CREATE TABLE Dweather (
  idDclim TEXT, idjourclim TEXT, annee INTEGER, mois INTEGER, jour INTEGER,
  jda INTEGER, tmin REAL, tmax REAL, tmoy REAL, rg REAL, etp REAL, plu REAL
);
CREATE TABLE ListPAnnexes (
  CodePosteAnnexe TEXT, altitude INTEGER, latitudeDD REAL, longitude REAL,
  idDclim TEXT, CO2c INTEGER, ConcNplu REAL, Codcc TEXT
);
CREATE TABLE ParamIni (
  IdIni TEXT, Stockinit REAL, Qpaillisinit REAL, iniSolhautON INTEGER, Ninit REAL
);
CREATE TABLE Tech_Commun (
  IdTech_Com TEXT, NbCult INTEGER, NomSC TEXT, SerreTunnelON INTEGER,
  imulch INTEGER, CodParamMulch INTEGER, QpaillisApport REAL, AltiCult INTEGER,
  IrrigON INTEGER, fertiminON INTEGER, fertiorgON INTEGER, tApportMON REAL,
  tApportMinN REAL, CsurN_AO REAL, KresY REAL, DriveRuiObs INTEGER
);
CREATE TABLE Tech_perCrop (
  idTechPerCrop TEXT, idTech_Com TEXT, NumCrop INTEGER, IdCultivar TEXT,
  TypInstal INTEGER, RepiquageON INTEGER, isem INTEGER, ilev INTEGER,
  DensSem REAL, irepiqu REAL, DensRepiqu REAL, DbutoirNouvSemis INTEGER,
  SemisAutoDebut INTEGER, SeuilCumPrecip REAL
);
CREATE TABLE SimUnitList (
  idsim TEXT, idTech_Com TEXT, idweather TEXT, idsoil TEXT, idIni TEXT,
  idGenParam TEXT, idCodModel INTEGER, StartYear INTEGER, StartDay INTEGER,
  EndYear INTEGER, EndDay INTEGER, codCC TEXT, ChampTri REAL, Situation TEXT,
  codesuite INTEGER
);
CREATE TABLE Soil (
  idsoil TEXT, NbCouches INTEGER, Zmes INTEGER, ZObstacleRac REAL, StockN REAL,
  CsurNhum REAL, TypeRui INTEGER, Clay REAL, pHeau REAL
);
CREATE TABLE Soil_layers (
  idsoil TEXT, NumCouche INTEGER, epc REAL, hcc REAL, hmin REAL, da REAL
);
CREATE TABLE Irrigation_List (
  IdTech_Com TEXT, IdIrrig TEXT, DateIrrig TEXT, YearIrrig INTEGER,
  JourYrIrrig INTEGER, Irrigation REAL
);
CREATE TABLE FertiMin_List (
  IdTech_Com TEXT, IdFertiMin TEXT, DateFertiMin TEXT, YearFertiMin INTEGER,
  JourYrFertiMin TEXT, Nmineral REAL, Pmineral REAL, Kmineral REAL
);
CREATE TABLE FertiOrga_List (
  IdTech_Com TEXT, IdFertiOrg TEXT, DateFertiOrg TEXT, YearFertiOrg INTEGER,
  JourYrFertiOrg TEXT, Norganique REAL, Porganique REAL, Korganique REAL,
  QorgaTot REAL, TypeMOrga TEXT, CsurNRes REAL
);
CREATE TABLE General_Parameters (idGenParam TEXT);
CREATE TABLE OptionsModel (
  idCodModel INTEGER, ActiveWstress INTEGER, ActiveNstress INTEGER,
  ActivePstress INTEGER, ActiveKstress INTEGER
);
INSERT INTO General_Parameters VALUES ('1');
"""


def make_target(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(TARGET_SCHEMA)


def rows(path, query, params=()):
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query, params)]


def test_soil_defaults_and_generic_overrides_use_model_dictionary(
    tmp_path, masterinput_copy, celsius_v32_template_db, modelsdictionary_db
):
    dictionary = tmp_path / "ModelsDictionary.db"
    shutil.copy2(modelsdictionary_db, dictionary)
    expected = {
        "PRedFact": 0.73,
        "Fmin": 0.31,
        "txminN": 1.7,
        "SeuilEvap": 0.64,
        "Zsurf": 42.0,
    }
    with sqlite3.connect(dictionary) as connection:
        for field, value in expected.items():
            result = connection.execute(
                "UPDATE Variables SET Default_Value_Datamill=? "
                "WHERE lower(model)='celsius' AND lower([Table])='soil' "
                "AND lower(Champ)=lower(?)",
                (str(value), field),
            )
            if result.rowcount == 0:
                connection.execute(
                    "INSERT INTO Variables "
                    "(model, [Table], Champ, Type, Default_Value_Datamill) "
                    "VALUES ('celsius', 'Soil', ?, 'Reel Double', ?)",
                    (field, str(value)),
                )

    with sqlite3.connect(masterinput_copy) as connection:
        soil_id = connection.execute(
            "SELECT idsoil FROM SimUnitList WHERE idsim=?",
            ("5.925_6.025_2001_FERT_MIN_ORG_2",),
        ).fetchone()
        assert soil_id is not None
        organic_c, organic_n_stock = connection.execute(
            "SELECT OrganicC, OrganicNStock FROM Soil WHERE IdSoil=?",
            (soil_id[0],),
        ).fetchone()
        connection.execute(
            "INSERT INTO SoilParameterOverrides "
            "(IdSoil, Model, TargetTable, Parameter, Value) "
            "VALUES (?, 'celsius', 'Soil', 'Zsurf', '47.0')",
            (soil_id[0],),
        )
        connection.execute(
            "INSERT INTO SoilParameterOverrides "
            "(IdSoil, Model, TargetTable, Parameter, Value) "
            "VALUES (?, 'celsius', 'Soil', 'StockN', '0.088')",
            (soil_id[0],),
        )

    target = tmp_path / "celsius-v32.db"
    shutil.copy2(celsius_v32_template_db, target)
    convert_database(
        masterinput_copy,
        target,
        simulation_ids=["5.925_6.025_2001_FERT_MIN_ORG_2"],
        models_dictionary=dictionary,
    )

    assert rows(
        target,
        "SELECT PRedFact, Fmin, txminN, SeuilEvap, Zsurf, StockN, CsurNhum "
        "FROM Soil "
        "WHERE idsoil=?",
        (soil_id[0],),
    ) == [{
        **expected,
        "Zsurf": 47.0,
        "StockN": 0.088,
        "CsurNhum": organic_c / organic_n_stock,
    }]


def test_soil_csur_nhum_requires_nonzero_organic_n_stock(
    tmp_path, masterinput_copy, celsius_v32_template_db, modelsdictionary_db
):
    with sqlite3.connect(masterinput_copy) as connection:
        soil_id = connection.execute(
            "SELECT idsoil FROM SimUnitList WHERE idsim=?",
            ("5.925_6.025_2001_FERT_MIN_ORG_2",),
        ).fetchone()[0]
        connection.execute(
            "UPDATE Soil SET OrganicNStock=0 WHERE IdSoil=?",
            (soil_id,),
        )

    target = tmp_path / "celsius-v32.db"
    shutil.copy2(celsius_v32_template_db, target)
    with pytest.raises(ValueError, match="OrganicNStock is zero"):
        convert_database(
            masterinput_copy,
            target,
            simulation_ids=["5.925_6.025_2001_FERT_MIN_ORG_2"],
            models_dictionary=modelsdictionary_db,
        )


def test_soil_stockn_accounts_for_topsoil_coarse_fragments(
    tmp_path, masterinput_copy, celsius_v32_template_db, modelsdictionary_db
):
    simulation = "5.925_6.025_2001_FERT_MIN_ORG_2"
    with sqlite3.connect(masterinput_copy) as connection:
        soil_id = connection.execute(
            "SELECT idsoil FROM SimUnitList WHERE idsim=?", (simulation,)
        ).fetchone()[0]
        organic_n_stock = connection.execute(
            "SELECT OrganicNStock FROM Soil WHERE IdSoil=?", (soil_id,)
        ).fetchone()[0]
        connection.execute("UPDATE Soil SET cf=25 WHERE IdSoil=?", (soil_id,))
        connection.execute(
            "UPDATE SoilLayers SET cf=25 WHERE lower(idsoil)=lower(?)", (soil_id,)
        )

    target = tmp_path / "celsius-v32.db"
    shutil.copy2(celsius_v32_template_db, target)
    convert_database(
        masterinput_copy,
        target,
        simulation_ids=[simulation],
        models_dictionary=modelsdictionary_db,
    )

    stock_n = rows(
        target, "SELECT StockN FROM Soil WHERE idsoil=?", (soil_id,)
    )[0]["StockN"]
    assert stock_n == pytest.approx(organic_n_stock * 0.75)


def test_topsoil_fine_earth_fraction_is_depth_weighted_over_30_cm():
    soil = {"cf": 10}
    layers = [
        {"Lup": 0, "Ldown": 10, "cf": 20},
        {"Lup": 10, "Ldown": 40, "cf": 40},
    ]

    # 10 cm at 80% fine earth plus 20 cm at 60% fine earth.
    assert core._topsoil_fine_earth_fraction(soil, layers) == pytest.approx(
        (10 * 0.8 + 20 * 0.6) / 30
    )


def test_successive_expands_seasons_and_preserves_associated_crops(
    tmp_path, masterinput_db, modelsdictionary_db
):
    target = tmp_path / "celsius-v32.db"
    make_target(target)

    convert_database(
        masterinput_db, target, mode="successive",
        models_dictionary=modelsdictionary_db,
    )

    simulations = rows(
        target, "SELECT * FROM SimUnitList ORDER BY ChampTri"
    )
    assert len(simulations) == 7
    rotation = [
        row for row in simulations
        if row["Situation"].endswith("ROT_MAIZE_PEANUT_3Y_2")
    ]
    assert [row["codesuite"] for row in rotation] == [0, 1, 1]
    assert [row["ChampTri"] for row in rotation] == [2.0, 3.0, 4.0]
    assert rotation[0]["EndYear"] == 2001
    # Season 2 starts with irrigation at sowing - 10 days (day 140).
    assert rotation[0]["EndDay"] == 139
    assert rotation[1]["StartYear"] == 2001
    assert rotation[1]["StartDay"] == 140
    assert rotation[1]["EndYear"] == 2002
    assert rotation[1]["EndDay"] == 149
    assert rotation[2]["StartYear"] == 2002
    assert rotation[2]["StartDay"] == 150
    assert rotation[2]["EndDay"] == 350

    first_standard = simulations[0]
    crops = rows(
        target,
        "SELECT NumCrop, IdCultivar FROM Tech_perCrop "
        "WHERE idTech_Com=? ORDER BY NumCrop",
        (first_standard["idTech_Com"],),
    )
    assert crops == [
        {"NumCrop": 1, "IdCultivar": "20.1"},
        {"NumCrop": 2, "IdCultivar": "2.1"},
    ]
    tech = rows(
        target,
        "SELECT NbCult FROM Tech_Commun WHERE IdTech_Com=?",
        (first_standard["idTech_Com"],),
    )
    assert tech[0]["NbCult"] == 2


def test_successive_converts_weather_soils_options_and_operations(
    tmp_path, masterinput_db, modelsdictionary_db
):
    target = tmp_path / "celsius-v32.db"
    make_target(target)

    convert_database(
        masterinput_db, target, mode="successive",
        models_dictionary=modelsdictionary_db,
    )

    assert rows(target, "SELECT COUNT(*) AS n FROM Dweather")[0]["n"] == 1096
    assert rows(target, "SELECT COUNT(*) AS n FROM Soil_layers")[0]["n"] == 2
    assert rows(target, "SELECT NbCouches FROM Soil")[0]["NbCouches"] == 2
    assert rows(target, "SELECT COUNT(*) AS n FROM Irrigation_List")[0]["n"] == 3
    assert rows(target, "SELECT COUNT(*) AS n FROM OptionsModel")[0]["n"] == 1


def test_standard_rejects_a_multi_season_management(
    tmp_path, masterinput_db, modelsdictionary_db
):
    target = tmp_path / "celsius-v32.db"
    make_target(target)

    with pytest.raises(ValueError, match="use celsius_mode='successive'"):
        convert_database(
            masterinput_db, target, mode="standard",
            models_dictionary=modelsdictionary_db,
        )


def test_standard_keeps_one_simulation_and_two_associated_crops(
    masterinput_copy, tmp_path, modelsdictionary_db
):
    master = masterinput_copy
    with sqlite3.connect(master) as connection:
        connection.execute(
            "DELETE FROM SimUnitList WHERE idMangt <> 'Mgt1M0_135'"
        )
        connection.commit()
    target = tmp_path / "celsius-v32.db"
    make_target(target)

    convert_database(
        master, target, mode="standard",
        models_dictionary=modelsdictionary_db,
    )

    simulations = rows(target, "SELECT * FROM SimUnitList ORDER BY ChampTri")
    assert len(simulations) == 3
    assert {row["codesuite"] for row in simulations} == {0}
    assert rows(target, "SELECT DISTINCT NbCult FROM Tech_Commun") == [
        {"NbCult": 2}
    ]


@pytest.mark.parametrize(
    ("dailyoutput", "expected"),
    [(None, 0), (0, 0), (1, 1), ("1", 1)],
)
def test_run_enables_daily_output_only_when_dailyoutput_is_one(
    tmp_path, monkeypatch, dailyoutput, expected, masterinput_copy,
    celsius_v32_template_db, modelsdictionary_db,
):
    from modfilegen import GlobalVariables
    from modfilegen.Converter.CelsiusV32Converter.runner import run

    master = masterinput_copy
    output = tmp_path / "celsius_v32.db"
    with sqlite3.connect(master) as connection:
        idsim = connection.execute(
            "SELECT idsim FROM SimUnitList ORDER BY idsim LIMIT 1"
        ).fetchone()[0]

    settings = {
        "dbMasterInput": str(master),
        "dbModelsDictionary": str(modelsdictionary_db),
        "dbCelsiusV32Template": str(celsius_v32_template_db),
        "celsiusV32Output": str(output),
        "celsiusIdsim": idsim,
        "runCelsiusV32": 0,
        "dt": 0,
    }
    for name, value in settings.items():
        monkeypatch.setitem(GlobalVariables, name, value)
    if dailyoutput is None:
        monkeypatch.delitem(GlobalVariables, "dailyoutput", raising=False)
    else:
        monkeypatch.setitem(GlobalVariables, "dailyoutput", dailyoutput)

    run("standard")

    assert rows(output, "SELECT DISTINCT EcritDResus FROM OptionsModel") == [
        {"EcritDResus": expected}
    ]


FAKE_ENGINE = """#!{python}
import sqlite3, sys
db = sys.argv[1]
with sqlite3.connect(db) as c:
    c.execute("CREATE TABLE IF NOT EXISTS OutputSynt (Idsim TEXT, LAI REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS OutputD_1 (IdSimJ TEXT, idSim TEXT, Jul INTEGER)")
    c.execute("DELETE FROM OutputSynt")
    c.execute("DELETE FROM OutputD_1")
    rows = c.execute(
        "SELECT idsim, codesuite, idTech_Com FROM SimUnitList ORDER BY ChampTri"
    ).fetchall()
    if rows and int(rows[0][1] or 0) != 0:
        sys.exit(3)  # a chain of successive simulations was split
    techs = {{row[0] for row in c.execute("SELECT IdTech_Com FROM Tech_Commun")}}
    if techs != {{row[2] for row in rows}}:
        sys.exit(4)  # management rows of other workers were not removed
    for idsim, _, _ in rows:
        c.execute("INSERT INTO OutputSynt (Idsim, LAI) VALUES (?, ?)", (idsim, len(idsim)))
        for day in (1, 2):
            c.execute("INSERT INTO OutputD_1 (IdSimJ, idSim, Jul) VALUES (?, ?, ?)", (f"{{idsim}} {{day}}", idsim, day))
"""


def make_fake_engine(tmp_path, body=FAKE_ENGINE):
    """A stand-in for the CELSIUS V32 executable.

    Windows has no shebang, so a chmod +x script there is not an executable
    at all and CreateProcess refuses it with "%1 is not a valid Win32
    application". The script therefore gets a .bat wrapper on Windows, which
    is also what a real engine shipped as a wrapper would look like.
    """
    import os
    import stat
    import sys

    script = tmp_path / "fake_celsius.py"
    script.write_text(body.format(python=sys.executable), encoding="utf-8")

    if os.name == "nt":
        engine = tmp_path / "fake_celsius.bat"
        engine.write_text(
            f'@"{sys.executable}" "{script}" %*\n', encoding="utf-8"
        )
        return str(engine)

    engine = tmp_path / "fake_celsius"
    engine.write_text(body.format(python=sys.executable), encoding="utf-8")
    engine.chmod(engine.stat().st_mode | stat.S_IEXEC)
    return str(engine)


STANDARD_SIMULATIONS = 4  # single-season simulations in the MasterInput fixture


def test_successive_management_pattern_repeats_until_simunit_end():
    simulation = {
        "idsim": "long-rotation",
        "idMangt": "rotation",
        "StartYear": 2000,
        "StartDay": 1,
        "EndYear": 2005,
        "EndDay": 365,
    }
    seasons = {
        1: [{
            "SeasonOrder": 1,
            "PlantOrder": 1,
            "SeasonYearOffset": 0,
            "sowingdate": 100,
            "DHarvest": 80,
        }],
        2: [{
            "SeasonOrder": 2,
            "PlantOrder": 1,
            "SeasonYearOffset": 1,
            "sowingdate": 150,
            "DHarvest": 80,
        }],
    }
    with sqlite3.connect(":memory:") as source:
        definitions = core._season_definitions(
            source, simulation, seasons, "successive"
        )

    assert [item["season_order"] for item in definitions] == list(range(1, 7))
    assert [item["template_season_order"] for item in definitions] == [
        1, 2, 1, 2, 1, 2,
    ]
    assert [item["season_year_offset"] for item in definitions] == list(range(6))
    assert definitions[0]["start"] == date(2000, 1, 1)
    assert definitions[-1]["end"] == date(2005, 12, 31)


def make_standard_database(
    tmp_path, master, template, models_dictionary,
    count=STANDARD_SIMULATIONS,
):
    database = tmp_path / "standard.db"
    shutil.copy2(template, database)
    with sqlite3.connect(master) as connection:
        ids = [
            row[0]
            for row in connection.execute(
                "SELECT idsim FROM SimUnitList WHERE idMangt NOT IN "
                "(SELECT idMangt FROM CropManagement WHERE SeasonOrder > 1) "
                "ORDER BY idsim LIMIT ?",
                (count,),
            )
        ]
    assert len(ids) == count
    convert_database(
        master, database, simulation_ids=ids,
        models_dictionary=models_dictionary,
    )
    return database


def outputs(path):
    return (
        rows(path, "SELECT Idsim, LAI FROM OutputSynt ORDER BY rowid"),
        rows(path, "SELECT IdSimJ, idSim, Jul FROM OutputD_1 ORDER BY rowid"),
    )


def test_partition_keeps_chains_whole_and_balances_parts():
    from modfilegen.Converter.CelsiusV32Converter.runner import _partition_chains

    chains = [[1, 2, 3], [4], [5, 6], [7], [8, 9, 10]]
    parts = _partition_chains(chains, 3)
    assert [row for part in parts for row in part] == list(range(1, 11))
    assert len(parts) == 3
    for chain in chains:
        assert sum(set(chain) <= set(part) for part in parts) == 1
    assert _partition_chains(chains, 20) == [[1, 2, 3], [4], [5, 6], [7], [8, 9, 10]]
    assert _partition_chains(chains, 1) == [list(range(1, 11))]


def test_conversion_indexes_per_simulation_lookups(
    tmp_path, masterinput_db, celsius_v32_template_db, modelsdictionary_db
):
    database = make_standard_database(
        tmp_path, masterinput_db, celsius_v32_template_db,
        modelsdictionary_db, count=1,
    )
    indexes = {
        row["tbl_name"]
        for row in rows(
            database,
            "SELECT tbl_name FROM sqlite_master "
            "WHERE type='index' AND name LIKE 'ix_modfilegen_%'",
        )
    }
    assert {"Dweather", "Tech_perCrop", "Soil_layers", "StadePheno"} <= indexes


def test_parallel_run_matches_a_single_process(
    tmp_path, masterinput_db, celsius_v32_template_db, modelsdictionary_db
):
    from modfilegen.Converter.CelsiusV32Converter.runner import run_model

    engine = make_fake_engine(tmp_path)
    single = make_standard_database(
        tmp_path, masterinput_db, celsius_v32_template_db, modelsdictionary_db
    )
    parallel = tmp_path / "parallel.db"
    shutil.copy2(single, parallel)

    run_model(single, engine, workers=1)
    run_model(parallel, engine, workers=3)

    assert outputs(parallel) == outputs(single)
    assert len(outputs(parallel)[0]) == STANDARD_SIMULATIONS
    assert not list(tmp_path.glob("parallel_workers_*"))


def test_parallel_run_never_splits_successive_chains(
    tmp_path, masterinput_db, modelsdictionary_db, monkeypatch
):
    from modfilegen.Converter.CelsiusV32Converter import runner

    run_model = runner.run_model

    target = tmp_path / "successive.db"
    make_target(target)
    convert_database(
        masterinput_db, target, mode="successive",
        models_dictionary=modelsdictionary_db,
    )
    engine = make_fake_engine(tmp_path)

    run_model(target, engine, workers=4)

    expected = [row["idsim"] for row in rows(target, "SELECT idsim FROM SimUnitList ORDER BY ChampTri")]
    assert [row["Idsim"] for row in outputs(target)[0]] == expected

    monkeypatch.setattr(
        runner,
        "transform_summary_dataframe",
        lambda dataframe, *_args, **_kwargs: dataframe,
    )
    summary = runner._summary_dataframe(
        masterinput_db, target, object(), "legacy"
    )
    rotation = summary[
        summary["Idsim"].str.endswith("ROT_MAIZE_PEANUT_3Y_2")
    ]
    assert rotation["SeasonOrder"].tolist() == [1, 2, 3]
    assert rotation["time"].tolist() == [2000, 2001, 2002]


def test_celsius_occurrence_time_is_the_actual_sowing_year():
    from modfilegen.Converter.CelsiusV32Converter.runner import (
        _occurrence_sowing_year,
    )

    assert _occurrence_sowing_year(1978, 190) == 1978
    assert _occurrence_sowing_year(1979, 370) == 1980


def test_parallel_run_failure_keeps_worker_files(
    tmp_path, masterinput_db, celsius_v32_template_db, modelsdictionary_db
):
    from modfilegen.Converter.CelsiusV32Converter.runner import run_model

    engine = make_fake_engine(
        tmp_path, "#!{python}\nimport sys\nprint('engine exploded')\nsys.exit(2)\n"
    )
    database = make_standard_database(
        tmp_path, masterinput_db, celsius_v32_template_db, modelsdictionary_db
    )

    with pytest.raises(RuntimeError, match="engine exploded"):
        run_model(database, engine, workers=2)
    work_dirs = list(tmp_path.glob("standard_workers_*"))
    assert len(work_dirs) == 1
    assert len(list(work_dirs[0].glob("part_*.log"))) == 2


def test_fertilisation_scenario_fills_celsius_input_lists(
    masterinput_db, celsius_v32_template_db, modelsdictionary_db, tmp_path
):
    target = tmp_path / "celsius-v32.db"
    shutil.copy2(celsius_v32_template_db, target)

    convert_database(
        masterinput_db,
        target,
        mode="standard",
        simulation_ids=["5.925_6.025_2001_FERT_MIN_ORG_2"],
        models_dictionary=modelsdictionary_db,
    )

    tech_id = "5.925_6.025_2001_FERT_MIN_ORG_2"
    assert rows(
        target,
        "SELECT fertiminON, fertiorgON, tApportMinN FROM Tech_Commun WHERE IdTech_Com=?",
        (tech_id,),
    ) == [{"fertiminON": 1, "fertiorgON": 1, "tApportMinN": 80.0}]
    # Sowing on day 150 of 2001; mineral inputs at +0 and +40 days.
    assert rows(
        target,
        # The V32 template declares JourYr* columns as TEXT.
        "SELECT YearFertiMin, CAST(JourYrFertiMin AS INTEGER) AS JourYrFertiMin, "
        "Nmineral FROM FertiMin_List WHERE IdTech_Com=? ORDER BY 2",
        (tech_id,),
    ) == [
        {"YearFertiMin": 2001, "JourYrFertiMin": 150, "Nmineral": 40.0},
        {"YearFertiMin": 2001, "JourYrFertiMin": 190, "Nmineral": 40.0},
    ]
    # Organic inputs 15 and 5 days before sowing, N = NFerti * Qmanure.
    assert rows(
        target,
        "SELECT CAST(JourYrFertiOrg AS INTEGER) AS JourYrFertiOrg, QorgaTot, "
        "round(Norganique, 6) AS N FROM FertiOrga_List WHERE IdTech_Com=? ORDER BY 1",
        (tech_id,),
    ) == [
        {"JourYrFertiOrg": 135, "QorgaTot": 1000.0, "N": 20.0},
        {"JourYrFertiOrg": 145, "QorgaTot": 500.0, "N": 5.0},
    ]


def _converted_type_rui(master, template, dictionary, tmp_path):
    target = tmp_path / "celsius-v32.db"
    shutil.copy2(template, target)
    convert_database(
        master, target, mode="standard",
        simulation_ids=["5.925_6.025_2001_FERT_MIN_ORG_2"],
        models_dictionary=dictionary,
    )
    return rows(target, "SELECT TypeRui FROM Soil")[0]["TypeRui"]


def test_type_rui_is_the_celsius_code_of_the_runoff_type(
    masterinput_copy, celsius_v32_template_db, modelsdictionary_db, tmp_path
):
    # MasterInput RunoffType 2 (moderate runoff) is CELSIUS TypeRui 6; the
    # soil code may be stored as a number while RunoffTypes holds text.
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute("UPDATE Soil SET RunoffType = 2.0")
    assert _converted_type_rui(
        masterinput_copy, celsius_v32_template_db, modelsdictionary_db, tmp_path
    ) == 6


def test_missing_celsius_runoff_code_is_an_error(
    masterinput_copy, celsius_v32_template_db, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute("UPDATE RunoffTypes SET CodRunoffCelsius = NULL WHERE RunoffType = '1'")
    with pytest.raises(ValueError, match="No RunoffTypes.CodRunoffCelsius for RunoffType"):
        _converted_type_rui(
            masterinput_copy, celsius_v32_template_db, modelsdictionary_db, tmp_path
        )


def test_databases_without_celsius_runoff_codes_keep_the_runoff_type(
    masterinput_copy, celsius_v32_template_db, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute("UPDATE Soil SET RunoffType = 2")
        connection.execute("ALTER TABLE RunoffTypes DROP COLUMN CodRunoffCelsius")
    assert _converted_type_rui(
        masterinput_copy, celsius_v32_template_db, modelsdictionary_db, tmp_path
    ) == 2
