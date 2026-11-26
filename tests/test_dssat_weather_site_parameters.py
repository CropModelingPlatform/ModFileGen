"""DSSAT weather headers: TAV and AMP come from Coordinates, else ModelsDictionary."""

import os
import sqlite3

import pytest

from modfilegen.Converter.DssatConverter import dssatweatherconverter as standard
from modfilegen.Converter.DssatConverter import dssatweatherconverter_v2 as successive

POINT = "5.925_6.025"
DEFAULT_TAV, DEFAULT_AMP = 27.7, 5.2  # ModelsDictionary fixture defaults


def _header_values(content):
    """Return (TAV, AMP) from the line following the '@ INSI' header."""
    lines = content.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("@ INSI"))
    fields = lines[index + 1].split()
    return float(fields[4]), float(fields[5])


def _export(module, masterinput, modelsdictionary, tmp_path):
    directory = os.path.join(str(tmp_path), "sim", POINT, "2001", "FERT_MIN_ORG")
    usmdir = tmp_path / "usm"
    usmdir.mkdir(exist_ok=True)
    with sqlite3.connect(masterinput) as mi, sqlite3.connect(modelsdictionary) as md:
        if module is standard:
            files = standard.DssatweatherConverter().export(
                directory, md, mi, str(usmdir), 0
            )
        else:
            files = successive.DssatweatherConverter().export_years(
                directory, md, mi, str(usmdir), years=[2001]
            )
    assert files
    return [_header_values(content) for content in files.values()]


@pytest.mark.parametrize("module", [standard, successive], ids=["standard", "successive"])
def test_null_coordinates_use_modelsdictionary_defaults(
    module, masterinput_copy, modelsdictionary_db, tmp_path
):
    headers = _export(module, masterinput_copy, modelsdictionary_db, tmp_path)
    assert set(headers) == {(DEFAULT_TAV, DEFAULT_AMP)}


@pytest.mark.parametrize("module", [standard, successive], ids=["standard", "successive"])
def test_coordinates_values_override_the_defaults(
    module, masterinput_copy, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute(
            "UPDATE Coordinates SET tav = 25.3, amp = 8.1 WHERE idPoint = ?", (POINT,)
        )
    headers = _export(module, masterinput_copy, modelsdictionary_db, tmp_path)
    assert set(headers) == {(25.3, 8.1)}


@pytest.mark.parametrize("module", [standard, successive], ids=["standard", "successive"])
def test_one_missing_value_falls_back_alone(
    module, masterinput_copy, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute("UPDATE Coordinates SET tav = 25.3 WHERE idPoint = ?", (POINT,))
    headers = _export(module, masterinput_copy, modelsdictionary_db, tmp_path)
    assert set(headers) == {(25.3, DEFAULT_AMP)}


@pytest.mark.parametrize("module", [standard, successive], ids=["standard", "successive"])
def test_databases_without_the_columns_keep_working(
    module, masterinput_copy, modelsdictionary_db, tmp_path
):
    with sqlite3.connect(masterinput_copy) as connection:
        connection.execute("ALTER TABLE Coordinates DROP COLUMN tav")
        connection.execute("ALTER TABLE Coordinates DROP COLUMN amp")
    headers = _export(module, masterinput_copy, modelsdictionary_db, tmp_path)
    assert set(headers) == {(DEFAULT_TAV, DEFAULT_AMP)}
