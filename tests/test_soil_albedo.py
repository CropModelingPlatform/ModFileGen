"""Soil albedo: measured Soil.albedo or re-estimated from the soil texture."""

import sqlite3

import pytest

from modfilegen.soil_repository import (
    DEFAULT_ALBEDO,
    SoilDataRepository,
    texture_albedo,
)

SOIL = "5.925_6.025"


@pytest.mark.parametrize(
    ("texture", "expected"),
    [("clay", 0.28), (" Clay Loam ", 0.20), ("clayey loam", 0.20), ("LOAM", 0.225),
     ("loamy sand", 0.25), ("sandy clay loam", DEFAULT_ALBEDO), (None, DEFAULT_ALBEDO)],
)
def test_texture_albedo(texture, expected):
    assert texture_albedo(texture) == expected


def _clay_soil(masterinput):
    with sqlite3.connect(masterinput) as connection:
        connection.execute("UPDATE Soil SET SoilTextureType = 'Clay', albedo = 0.12")


@pytest.mark.parametrize(("strategy", "expected"), [("measured", 0.12), ("texture", 0.28)])
def test_repository_applies_the_albedo_strategy(masterinput_copy, strategy, expected):
    _clay_soil(masterinput_copy)
    with sqlite3.connect(masterinput_copy) as connection:
        soils = SoilDataRepository(connection, strategy)
        soils.prefetch([SOIL])
        assert soils.get_soil(SOIL)["albedo"] == expected


def test_unknown_albedo_strategy_is_an_error(masterinput_copy):
    with sqlite3.connect(masterinput_copy) as connection:
        with pytest.raises(ValueError, match="albedoStrategy must be one of"):
            SoilDataRepository(connection, "estimated")


def test_dssat_and_stics_v11_write_the_texture_albedo(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    from modfilegen.Converter.DssatConverter import dssatsoilconverter
    from modfilegen.Converter.SticsV11Converter.sticsparamsolconverter import (
        SticsParamSolConverter,
    )
    from modfilegen.coordinate_resolver import CoordinateResolver
    from modfilegen.parameter_resolver import ParameterResolver

    _clay_soil(masterinput_copy)
    with sqlite3.connect(masterinput_copy) as mi, sqlite3.connect(modelsdictionary_db) as md:
        soils = SoilDataRepository(mi, "texture")
        soils.prefetch([SOIL])
        resolver = ParameterResolver(md, mi)
        resolver.prefetch("dssat", dssatsoilconverter.PARAMETER_TABLES, [SOIL])
        resolver.prefetch("sticsv11", {"paramsol"}, [SOIL])
        coordinates = CoordinateResolver(mi)
        coordinates.prefetch([SOIL])
        dssat = dssatsoilconverter.DssatSoilConverter().export(
            resolver, soils, str(tmp_path), SOIL, "Mgt1", coordinates.resolve(SOIL))
        stics = SticsParamSolConverter().export(resolver, soils, str(tmp_path), SOIL)

    lines = dssat.splitlines()
    salb = lines[next(i for i, line in enumerate(lines) if line.startswith("@ SCOM")) + 1].split()[1]
    assert salb == "0.28"
    # param.sol line 1: albedo is the 9th field (after "1" and "Sol").
    assert stics.splitlines()[0].split()[8] == "0.2800"


def test_repository_follows_the_global_albedo_strategy(masterinput_copy, monkeypatch):
    from modfilegen import GlobalVariables

    _clay_soil(masterinput_copy)
    monkeypatch.setitem(GlobalVariables, "albedoStrategy", "texture")
    with sqlite3.connect(masterinput_copy) as connection:
        soils = SoilDataRepository(connection)
        soils.prefetch([SOIL])
        assert soils.get_soil(SOIL)["albedo"] == 0.28
