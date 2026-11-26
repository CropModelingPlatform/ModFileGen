import math

from modfilegen.Converter.DssatConverter.dssatsoilconverter import resolve_ssat


def test_resolve_ssat_prefers_soil_value():
    assert resolve_ssat(52, 30) == 0.52


def test_resolve_ssat_uses_wfc_fallback_for_missing_value():
    assert math.isclose(resolve_ssat(None, 30), 0.303)
    assert math.isclose(resolve_ssat(float("nan"), 30), 0.303)


def test_resolve_ssat_does_not_treat_zero_as_missing():
    assert resolve_ssat(0, 30) == 0


def test_resolve_ssat_prefers_layer_value():
    assert resolve_ssat(52, 30, 47) == 0.47


def test_resolve_ssat_layer_falls_back_to_soil_then_wfc():
    assert resolve_ssat(52, 30, None) == 0.52
    assert math.isclose(resolve_ssat(None, 30, None), 0.303)


import sqlite3

import pytest

from modfilegen.Converter.DssatConverter import dssatsoilconverter, dssatxconverter
from modfilegen.coordinate_resolver import CoordinateResolver
from modfilegen.parameter_resolver import ParameterResolver
from modfilegen.soil_repository import SoilDataRepository

SOIL, POINT = "5.925_6.025", "5.925_6.025"


def _soil_file(masterinput, modelsdictionary, tmp_path, option="detailed", overrides=()):
    with sqlite3.connect(masterinput) as connection:
        connection.execute("UPDATE Soil SET SoilOption = ?", (option,))
        connection.executemany(
            "INSERT INTO SoilParameterOverrides "
            "(IdSoil, Model, TargetTable, Parameter, Value, NumLayer) "
            "VALUES (?, 'dssat', ?, ?, ?, ?)",
            [(SOIL, *override) for override in overrides],
        )
    with sqlite3.connect(masterinput) as mi, sqlite3.connect(modelsdictionary) as md:
        resolver = ParameterResolver(md, mi)
        resolver.prefetch("dssat", dssatsoilconverter.PARAMETER_TABLES, {SOIL})
        soils = SoilDataRepository(mi)
        soils.prefetch({SOIL})
        coordinates = CoordinateResolver(mi)
        coordinates.prefetch({POINT})
        return dssatsoilconverter.DssatSoilConverter().export(
            resolver, soils, str(tmp_path), SOIL, "FERT_MIN_ORG", coordinates.resolve(POINT)
        )


def _layers(content):
    """Return the layer rows of the first @SLB table as {column: text}."""
    lines = content.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("@  SLB  SLMH"))
    header = lines[start][1:].split()
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("@") or not line.strip():
            break
        rows.append(dict(zip(header, line.split())))
    return rows


def _initial_water_rows(masterinput, modelsdictionary):
    with sqlite3.connect(masterinput) as mi, sqlite3.connect(modelsdictionary) as md:
        resolver = ParameterResolver(md, mi)
        resolver.prefetch("dssat", dssatsoilconverter.PARAMETER_TABLES, {SOIL})
        content = dssatxconverter.writeBlockInitialConditionData(
            "dssat_x_initial_condition_data",
            "5.925_6.025_2000_Mgt1M0_150_2",
            md,
            mi,
            resolver,
        )
    return [line.split() for line in content.splitlines()[1:]]


def test_soil_file_uses_site_code_coordinates_and_measured_layers(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    content = _soil_file(masterinput_copy, modelsdictionary_db, tmp_path)

    assert "*XXFERT0101" in content
    assert " XXFERT0101  NoCountry      5.925    6.025" in content
    layers = _layers(content)
    assert [row["SLB"] for row in layers] == ["30", "145"]
    assert [row["SDUL"] for row in layers] == ["0.300", "0.294"]
    assert [row["SSKS"] for row in layers] == ["2.590", "2.590"]
    assert (tmp_path / "XX.SOL").read_text() == content


def test_layer_and_profile_overrides(masterinput_copy, modelsdictionary_db, tmp_path):
    content = _soil_file(masterinput_copy, modelsdictionary_db, tmp_path, overrides=[
        ("dssat_soil_data", "ssks", "4.5", 0),
        ("dssat_soil_data", "ssks", "9", 2),
        ("dssat_soil_data", "sdul", "0.25", 1),
        ("dssat_soil_site", "scom", "BN", 0),
    ])

    layers = _layers(content)
    assert [row["SSKS"] for row in layers] == ["4.500", "9.000"]
    # A measured property is replaced only on the overridden layer.
    assert [row["SDUL"] for row in layers] == ["0.250", "0.294"]
    assert "\n    BN  " in content


def test_measured_water_contents_are_corrected_for_coarse_fragments(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute(
            "UPDATE SoilLayers SET cf = 25, Wwp = 10, Wfc = 30, Ssat = 50"
        )

    layers = _layers(_soil_file(
        masterinput_copy, modelsdictionary_db, tmp_path
    ))

    assert [row["SLLL"] for row in layers] == ["0.075", "0.075"]
    assert [row["SDUL"] for row in layers] == ["0.225", "0.225"]
    assert [row["SSAT"] for row in layers] == ["0.375", "0.375"]


def test_dssat_water_overrides_are_not_fine_earth_corrected(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute(
            "UPDATE SoilLayers SET cf = 25, Wwp = 10, Wfc = 30, Ssat = 50"
        )

    layers = _layers(_soil_file(
        masterinput_copy,
        modelsdictionary_db,
        tmp_path,
        overrides=[
            ("dssat_soil_data", "slll", "0.12", 1),
            ("dssat_soil_data", "sdul", "0.25", 1),
            ("dssat_soil_data", "ssat", "0.45", 1),
        ],
    ))

    assert (layers[0]["SLLL"], layers[0]["SDUL"], layers[0]["SSAT"]) == (
        "0.120", "0.250", "0.450"
    )
    assert (layers[1]["SLLL"], layers[1]["SDUL"], layers[1]["SSAT"]) == (
        "0.075", "0.225", "0.375"
    )


def test_slcf_override_controls_fine_earth_corrections(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute(
            "UPDATE SoilLayers SET cf = 10, Wwp = 10, Wfc = 30, Ssat = 50, "
            "OrganicC = 2, TotalN = 0.2"
        )

    layers = _layers(_soil_file(
        masterinput_copy,
        modelsdictionary_db,
        tmp_path,
        overrides=[("dssat_soil_data", "slcf", "25", 1)],
    ))

    assert layers[0]["SLCF"] == "25.0"
    assert layers[0]["SDUL"] == "0.225"
    assert layers[0]["SLOC"] == "1.500"
    assert layers[0]["SLNI"] == "0.15"


def test_measured_carbon_and_nitrogen_are_corrected_for_coarse_fragments(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute(
            "UPDATE SoilLayers SET cf = 25, OrganicC = 2, TotalN = 0.2"
        )

    layers = _layers(_soil_file(
        masterinput_copy, modelsdictionary_db, tmp_path
    ))

    assert [row["SLCF"] for row in layers] == ["25.0", "25.0"]
    assert [row["SLOC"] for row in layers] == ["1.500", "1.500"]
    assert [row["SLNI"] for row in layers] == ["0.15", "0.15"]


def test_dssat_carbon_and_nitrogen_overrides_are_not_fine_earth_corrected(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute(
            "UPDATE SoilLayers SET cf = 25, OrganicC = 2, TotalN = 0.2"
        )

    layers = _layers(_soil_file(
        masterinput_copy,
        modelsdictionary_db,
        tmp_path,
        overrides=[
            ("dssat_soil_data", "sloc", "3", 1),
            ("dssat_soil_data", "slni", "0.3", 1),
        ],
    ))

    assert layers[0]["SLOC"] == "3.000"
    assert layers[0]["SLNI"] == "0.30"
    assert layers[1]["SLOC"] == "1.500"
    assert layers[1]["SLNI"] == "0.15"


def test_simple_soil_uses_profile_cf_for_carbon_and_nitrogen(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute(
            "UPDATE Soil SET cf = 20, OrganicC = 2, OrganicNStock = 0.2, "
            "Wwp = 10, Wfc = 30, Ssat = 50"
        )

    layers = _layers(_soil_file(
        masterinput_copy, modelsdictionary_db, tmp_path, option="simple"
    ))

    assert layers[0]["SLCF"] == "20.0"
    assert layers[0]["SLLL"] == "0.080"
    assert layers[0]["SDUL"] == "0.240"
    assert layers[0]["SSAT"] == "0.400"
    assert layers[0]["SLOC"] == "1.600"
    assert layers[0]["SLNI"] == "0.16"


def test_simple_soil_initial_water_uses_whole_soil_limits(
    masterinput_copy, modelsdictionary_db
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute(
            "UPDATE Soil SET SoilOption = 'simple', cf = 25, Wwp = 10, Wfc = 30"
        )
        connection.execute("UPDATE InitialConditions SET WStockinit = 50")

    rows = _initial_water_rows(masterinput_copy, modelsdictionary_db)

    assert [row[2] for row in rows] == ["0.150", "0.150"]


def test_detailed_soil_initial_water_uses_each_layer_cf(
    masterinput_copy, modelsdictionary_db
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute("UPDATE Soil SET SoilOption = 'detailed', cf = 5")
        connection.execute(
            "UPDATE SoilLayers SET Wwp = 10, Wfc = 30, cf = 25 WHERE NumLayer = 1"
        )
        connection.execute(
            "UPDATE SoilLayers SET Wwp = 20, Wfc = 40, cf = NULL WHERE NumLayer = 2"
        )
        connection.execute("UPDATE InitialConditions SET WStockinit = 50")

    rows = _initial_water_rows(masterinput_copy, modelsdictionary_db)

    assert [row[2] for row in rows] == ["0.150", "0.285"]


def test_initial_water_uses_effective_dssat_limit_overrides(
    masterinput_copy, modelsdictionary_db
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute("UPDATE Soil SET SoilOption = 'detailed'")
        connection.execute(
            "UPDATE SoilLayers SET Wwp = 10, Wfc = 30, cf = 10"
        )
        connection.execute("UPDATE InitialConditions SET WStockinit = 50")
        connection.executemany(
            "INSERT INTO SoilParameterOverrides "
            "(IdSoil, Model, TargetTable, Parameter, Value, NumLayer) "
            "VALUES (?, 'dssat', 'dssat_soil_data', ?, ?, 1)",
            [(SOIL, "slcf", "25"), (SOIL, "slll", "0.12"),
             (SOIL, "sdul", "0.45")],
        )

    rows = _initial_water_rows(masterinput_copy, modelsdictionary_db)

    assert rows[0][2] == "0.285"
    # Layer 2 has no layer-specific override and uses its measured limits.
    assert rows[1][2] == "0.180"


def test_simple_soil_is_one_layer_written_on_two_lines(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    content = _soil_file(masterinput_copy, modelsdictionary_db, tmp_path, option="simple",
                         overrides=[("dssat_soil_data", "srgf", "0.5", 1)])

    assert [row["SRGF"] for row in _layers(content)] == ["0.500", "0.500"]


def test_override_errors(masterinput_copy, modelsdictionary_db, tmp_path):
    with pytest.raises(ValueError, match="layer 3 of soil"):
        _soil_file(masterinput_copy, modelsdictionary_db, tmp_path,
                   overrides=[("dssat_soil_data", "ssks", "9", 3)])


def test_site_parameter_cannot_target_a_layer(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    with pytest.raises(ValueError, match=r"whole-soil parameter\(s\) \['scom'\]"):
        _soil_file(masterinput_copy, modelsdictionary_db, tmp_path,
                   overrides=[("dssat_soil_site", "scom", "BN", 1)])


def _set_ssks(masterinput, soil, layer1, layer2):
    with sqlite3.connect(masterinput) as connection:
        connection.execute("UPDATE Soil SET Ssks = ?", (soil,))
        connection.execute("UPDATE SoilLayers SET Ssks = ? WHERE NumLayer = 1", (layer1,))
        connection.execute("UPDATE SoilLayers SET Ssks = ? WHERE NumLayer = 2", (layer2,))


def test_simple_soil_writes_measured_soil_conductivity(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    _set_ssks(masterinput_copy, 1.5, None, None)
    content = _soil_file(masterinput_copy, modelsdictionary_db, tmp_path, option="simple")
    assert [row["SSKS"] for row in _layers(content)] == ["1.500", "1.500"]


def test_detailed_soil_conductivity_uses_layer_then_soil_then_override(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    _set_ssks(masterinput_copy, 1.5, 3.0, None)
    content = _soil_file(masterinput_copy, modelsdictionary_db, tmp_path)
    assert [row["SSKS"] for row in _layers(content)] == ["3.000", "1.500"]

    content = _soil_file(masterinput_copy, modelsdictionary_db, tmp_path,
                         overrides=[("dssat_soil_data", "ssks", "9", 1)])
    assert [row["SSKS"] for row in _layers(content)] == ["9.000", "1.500"]


def _sldr(content):
    lines = content.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("@ SCOM"))
    return lines[index + 1].split()[3]


def test_sldr_uses_modelsdictionary_without_fao_class(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    assert _sldr(_soil_file(masterinput_copy, modelsdictionary_db, tmp_path)) == "0.60"


@pytest.mark.parametrize(
    ("drain_fao", "expected"),
    [(1, "0.01"), (2, "0.05"), (3, "0.25"), (4, "0.40"), (5, "0.60"), (6, "0.75"), (7, "0.85")],
)
def test_sldr_is_derived_from_the_fao_drainage_class(
    masterinput_copy, modelsdictionary_db, tmp_path, drain_fao, expected
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute("UPDATE Soil SET DrainFAO = ?", (drain_fao,))
    assert _sldr(_soil_file(masterinput_copy, modelsdictionary_db, tmp_path)) == expected


def test_sldr_override_wins_over_the_fao_class(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute("UPDATE Soil SET DrainFAO = 2")
    content = _soil_file(masterinput_copy, modelsdictionary_db, tmp_path,
                         overrides=[("dssat_soil_site", "sldr", "0.33", 0)])
    assert _sldr(content) == "0.33"


def test_invalid_fao_drainage_class_is_an_error():
    with pytest.raises(ValueError, match="DrainFAO must be a class from 1 to 7"):
        dssatsoilconverter.drainage_rate({"sldr": "0.6"}, {"drainfao": 9}, False)


def test_dssat_crop_model_uses_current_crop_not_previous_crop(masterinput_copy, tmp_path):
    from modfilegen.Converter.DssatConverter.dssatcultivarconverter import DssatCultivarConverter

    # Previous crop (fallow) differs from the current crop (maize).
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute(
            "UPDATE ListCultOption SET PRCROP = 'FA', CG = 'MZ', DSCROP = 'CER047' "
            "WHERE CodePSpecies = 'testcult'"
        )
    plant_files = tmp_path / "plt"
    plant_files.mkdir()
    for extension in ("CUL", "ECO", "SPE"):
        (plant_files / f"MZCER048.{extension}").write_text(extension)
    usm = tmp_path / "usm"
    with sqlite3.connect(masterinput_copy) as connection:
        crop = DssatCultivarConverter().export(
            str(tmp_path / "sim" / "FERT_MIN_ORG"), connection, str(plant_files),
            str(usm), "v48",
        )

    assert crop == "MZ"
    assert sorted(path.name for path in usm.iterdir()) == [
        "MZCER048.CUL", "MZCER048.ECO", "MZCER048.SPE",
    ]
