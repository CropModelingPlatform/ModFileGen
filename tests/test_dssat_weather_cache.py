"""One weather file per point and year, not per rotation.

A weather file's content depends on the point and the year alone -- the
coordinates, TAV and AMP, and the RaClimateD rows. The rotation only decides
its name, since DSSAT takes the four-character station code from the
management. So a point carrying several rotations -- P1-P2-P3 and P1-P4-P5
are two managements of one point -- had the same bytes generated once per
rotation.

The cache lives in the worker process, so the groups are ordered by point:
loky keeps a worker across tasks but shares nothing between workers, and
without that order the cache would never hit.
"""

import pandas as pd
import pytest

from modfilegen.Converter.DssatConverter import dssatsuccessiveconverter as dssat


@pytest.fixture(autouse=True)
def empty_cache():
    dssat._WEATHER_BY_YEAR.clear()
    dssat._WEATHER_POINT = None
    yield
    dssat._WEATHER_BY_YEAR.clear()
    dssat._WEATHER_POINT = None


def simulations(points_and_managements):
    """SimUnitList rows, deliberately not ordered by point."""
    return [
        {
            "idsim": f"{point}_{management}", "idPoint": point,
            "idMangt": management, "StartYear": 2000, "StartDay": 120,
            "EndYear": 2002, "EndDay": 350, "idsoil": "s", "idIni": "i",
            "idOption": "o",
        }
        for point, management in points_and_managements
    ]


# --- the order that makes the cache possible ------------------------------


def test_the_groups_are_ordered_by_point():
    rows = simulations([
        ("p2", "ROT_A"), ("p1", "ROT_B"), ("p2", "ROT_C"), ("p1", "ROT_D"),
    ])

    groups = dssat.build_successive_groups(rows)

    assert [group[0]["idPoint"] for group in groups] == ["p1", "p1", "p2", "p2"]


def test_the_order_is_stable_within_a_point():
    """Two rotations of one point keep a defined order, so a run is
    reproducible."""
    rows = simulations([("p1", "ROT_B"), ("p1", "ROT_A")])

    groups = dssat.build_successive_groups(rows)

    assert [group[0]["idMangt"] for group in groups] == ["ROT_A", "ROT_B"]


def test_every_simulation_still_gets_its_own_group():
    rows = simulations([("p1", "A"), ("p1", "B"), ("p2", "C")])

    groups = dssat.build_successive_groups(rows)

    assert len(groups) == 3
    assert all(len(group) == 1 for group in groups)


# --- the cache ------------------------------------------------------------


def test_nothing_is_cached_to_begin_with():
    assert dssat.cached_weather("p1", [2000, 2001]) is None


def test_what_was_generated_comes_back_by_year():
    dssat.remember_weather(
        "p1", [2000, 2001],
        {"ROT_0001.WTH": "year 2000", "ROT_0101.WTH": "year 2001"},
    )

    assert dssat.cached_weather("p1", [2000, 2001]) == {
        2000: "year 2000", 2001: "year 2001",
    }


def test_another_rotation_of_the_same_point_reuses_it():
    """The whole point: same bytes, a different name."""
    dssat.remember_weather("p1", [2000], {"ROTA0001.WTH": "the same bytes"})

    assert dssat.cached_weather("p1", [2000]) == {2000: "the same bytes"}


def test_another_point_gets_nothing():
    dssat.remember_weather("p1", [2000], {"ROT_0001.WTH": "p1 weather"})

    assert dssat.cached_weather("p2", [2000]) is None


def test_changing_point_drops_the_previous_one():
    """Only one point is held, so the cache cannot grow with the database."""
    dssat.remember_weather("p1", [2000], {"ROT_0001.WTH": "p1"})
    dssat.remember_weather("p2", [2000], {"ROT_0001.WTH": "p2"})

    assert dssat.cached_weather("p2", [2000]) == {2000: "p2"}
    assert len(dssat._WEATHER_BY_YEAR) == 1


def test_a_missing_year_is_not_a_partial_hit():
    """A rotation needing 2000 to 2002 must not be given two of the three."""
    dssat.remember_weather(
        "p1", [2000, 2001], {"ROT_0001.WTH": "a", "ROT_0101.WTH": "b"}
    )

    assert dssat.cached_weather("p1", [2000, 2001, 2002]) is None
    assert dssat.cached_weather("p1", [2000, 2001]) is not None


def test_a_year_that_cannot_be_matched_is_not_stored():
    """The year is read back from the name; an unexpected shape is dropped
    rather than filed under a guess."""
    dssat.remember_weather("p1", [2000], {"unexpected.name": "content"})

    assert dssat.cached_weather("p1", [2000]) is None
