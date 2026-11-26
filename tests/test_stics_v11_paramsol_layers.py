"""STICS v11 param.sol layer parameters come from layer-wise soil overrides."""

import sqlite3

import pytest

from modfilegen.Converter.SticsV11Converter.sticsparamsolconverter import (
    SticsParamSolConverter,
)
from modfilegen.parameter_resolver import ParameterResolver
from modfilegen.soil_repository import SoilDataRepository

SOIL = "5.925_6.025"  # fixture soil with two SoilLayers rows
DEFAULTS = (10, 50, 10)  # ModelsDictionary typecailloux, infil, epd


def _param_sol(masterinput, modelsdictionary, tmp_path, soil_option, overrides):
    with sqlite3.connect(masterinput) as connection:
        connection.execute("UPDATE Soil SET SoilOption = ?", (soil_option,))
        connection.executemany(
            "INSERT INTO SoilParameterOverrides "
            "(IdSoil, Model, TargetTable, Parameter, Value, NumLayer) "
            "VALUES (?, 'sticsv11', 'paramsol', ?, ?, ?)",
            [(SOIL, *override) for override in overrides],
        )
    with sqlite3.connect(masterinput) as mi, sqlite3.connect(modelsdictionary) as md:
        resolver = ParameterResolver(md, mi)
        resolver.prefetch("sticsv11", {"paramsol"}, {SOIL})
        soils = SoilDataRepository(mi)
        soils.prefetch({SOIL})
        content = SticsParamSolConverter().export(resolver, soils, str(tmp_path), SOIL)
    # The five layer lines end with typecailloux, infil and epd.
    return [tuple(int(value) for value in line.split()[-3:])
            for line in content.splitlines()[-5:]]


def test_detailed_soil_uses_layer_then_profile_overrides(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    layers = _param_sol(masterinput_copy, modelsdictionary_db, tmp_path, "detailed", [
        ("epd", "4", 0),
        ("infil", "7", 2),
    ])

    assert layers == [(10, 50, 4), (10, 7, 4), (10, 50, 4), (10, 50, 4), (10, 50, 4)]


def test_simple_soil_has_one_layer(masterinput_copy, modelsdictionary_db, tmp_path):
    layers = _param_sol(masterinput_copy, modelsdictionary_db, tmp_path, "simple", [
        ("typecailloux", "2", 1),
    ])

    assert layers == [(2, 50, 10)] + [DEFAULTS] * 4


def test_override_beyond_the_soil_layers_is_an_error(
    masterinput_copy, modelsdictionary_db, tmp_path
):
    with pytest.raises(ValueError, match="layer 3 of soil"):
        _param_sol(masterinput_copy, modelsdictionary_db, tmp_path, "detailed", [
            ("infil", "7", 3),
        ])
