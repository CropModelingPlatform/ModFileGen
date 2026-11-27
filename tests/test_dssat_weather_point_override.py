"""A point override reaches the DSSAT weather header.

`PointParameterOverrides` is keyed by `(idPoint, Model, TargetTable,
Parameter)` and STICS v11's station writer has honoured it from the start.
DSSAT's weather writer did not, so the same database described two
different stations to the two models.

`WNDHT` is the field that makes this matter. It is the height at which the
weather was measured, which STICS calls `zr`, and the dictionary default of
2.0 m sits below a 2.5 m maize canopy -- the value we had to raise by hand
in the fixture. Imported from a weather file, it belongs to the point.
"""

import sqlite3

import pytest

from modfilegen.Converter.DssatConverter import dssatweatherconverter_v2 as weather
from modfilegen.parameter_resolver import ParameterResolver

POINT = "5.925_6.025"
TABLE = weather.WEATHER_SITE_TABLE


@pytest.fixture
def connections(masterinput_copy, modelsdictionary_db):
    master = sqlite3.connect(str(masterinput_copy))
    dictionary = sqlite3.connect(str(modelsdictionary_db))
    try:
        yield master, dictionary
    finally:
        master.close()
        dictionary.close()


def resolver_with(master, dictionary, overrides):
    """A resolver prefetched for this point, with `overrides` in place."""
    for parameter, value in overrides.items():
        master.execute(
            "INSERT OR REPLACE INTO PointParameterOverrides"
            " (idPoint, Model, TargetTable, Parameter, Value)"
            " VALUES (?, 'dssat', ?, ?, ?)",
            (POINT, TABLE, parameter, value),
        )
    master.commit()
    resolver = ParameterResolver(dictionary, master)
    resolver.prefetch_point("dssat", [TABLE], [POINT])
    return resolver


def header(tmp_path, master, dictionary, resolver):
    """The @ INSI line of a generated .WTH, as fields."""
    produced = weather.DssatweatherConverter().export_years(
        f"tmp/{POINT}/2001/ROT_MAIZE_PEANUT_3Y",
        dictionary, master, str(tmp_path), years=[2001],
        parameter_resolver=resolver,
    )
    content = next(iter(produced.values()))
    lines = content.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("@ INSI"))
    return dict(zip(lines[index][1:].split(), lines[index + 1].split()))


# --- the default, and the override ----------------------------------------


def test_without_an_override_the_dictionary_default_stands(
    tmp_path, connections
):
    master, dictionary = connections
    resolver = resolver_with(master, dictionary, {})

    assert header(tmp_path, master, dictionary, resolver)["WNDHT"] == "2.0"


def test_an_override_reaches_the_header(tmp_path, connections):
    """What an import of a real weather file would write."""
    master, dictionary = connections
    resolver = resolver_with(master, dictionary, {"wndht": "10.0"})

    assert header(tmp_path, master, dictionary, resolver)["WNDHT"] == "10.0"


def test_the_reference_height_is_overridable_too(tmp_path, connections):
    master, dictionary = connections
    resolver = resolver_with(master, dictionary, {"refht": "1.5"})

    assert header(tmp_path, master, dictionary, resolver)["REFHT"] == "1.5"


def test_an_override_wins_over_the_coordinates_column(tmp_path, connections):
    """The order the soil writers already use: a measured value stands
    unless someone overrode it on purpose. `Coordinates.tav` is the measured
    one here."""
    master, dictionary = connections
    master.execute(
        "UPDATE Coordinates SET tav = 27.7 WHERE idPoint = ?", (POINT,)
    )
    master.commit()
    resolver = resolver_with(master, dictionary, {"tav": "19.4"})

    assert header(tmp_path, master, dictionary, resolver)["TAV"] == "19.4"


def test_the_coordinates_column_stands_when_nothing_overrides_it(
    tmp_path, connections
):
    master, dictionary = connections
    master.execute(
        "UPDATE Coordinates SET tav = 27.7 WHERE idPoint = ?", (POINT,)
    )
    master.commit()
    resolver = resolver_with(master, dictionary, {})

    assert header(tmp_path, master, dictionary, resolver)["TAV"] == "27.7"


def test_another_point_is_not_affected(tmp_path, connections):
    """The key is the point, so an override must not leak to a neighbour."""
    master, dictionary = connections
    master.execute(
        "INSERT OR REPLACE INTO PointParameterOverrides"
        " (idPoint, Model, TargetTable, Parameter, Value)"
        " VALUES ('somewhere-else', 'dssat', ?, 'wndht', '99.0')",
        (TABLE,),
    )
    master.commit()
    resolver = ParameterResolver(dictionary, master)
    resolver.prefetch_point("dssat", [TABLE], [POINT, "somewhere-else"])

    assert header(tmp_path, master, dictionary, resolver)["WNDHT"] == "2.0"


def test_without_a_resolver_nothing_changes(tmp_path, connections):
    """Every caller that does not pass one keeps the behaviour it had."""
    master, dictionary = connections
    resolver_with(master, dictionary, {"wndht": "10.0"})

    assert header(tmp_path, master, dictionary, None)["WNDHT"] == "2.0"


# --- and the prefetch happens where it must -------------------------------


def test_the_prefetch_is_done_in_the_parent_process():
    """A loky worker re-imports the package and sees only the dictionary
    defaults, so prefetch_point has to run before the workers start."""
    from pathlib import Path

    root = Path(__file__).parent.parent / "src/modfilegen/Converter/DssatConverter"
    for name, before in (
        ("dssatconverter.py", "Parallel("),
        ("dssatsuccessiveconverter.py", "def process_successive_group"),
    ):
        source = (root / name).read_text(encoding="utf-8")
        assert "prefetch_point(" in source, name
        assert source.index("prefetch_point(") < source.index(before), (
            f"{name}: the point prefetch must come before {before}"
        )
