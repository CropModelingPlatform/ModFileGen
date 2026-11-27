"""Every SIMULATION CONTROLS sub-block is overridable per crop-season.

`dssat_x_simulation_method` was wired first, for MEPHO. The other four
followed, and `_management` is the one that carries `HARVS`: a season can
now ask to be harvested at maturity instead of on a reported date, which is
the equivalent of STICS's `codrecolte = 1` and the last known obstacle for
the fixture's peanut season.

Each writer asks for its own table, so an override of one cannot reach
another -- which matters because several sub-blocks share a parameter name
(`LNSIM` numbers all of them).
"""

import sqlite3

import pytest

from modfilegen.Converter.DssatConverter import dssatxconverter
from modfilegen.parameter_resolver import ParameterResolver

MANAGEMENT = "ROT_MAIZE_PEANUT_3Y"


@pytest.fixture
def connections(masterinput_copy, modelsdictionary_db):
    master = sqlite3.connect(str(masterinput_copy))
    dictionary = sqlite3.connect(str(modelsdictionary_db))
    try:
        yield master, dictionary
    finally:
        master.close()
        dictionary.close()


def resolver_with(master, dictionary, rows):
    """A resolver prefetched for every overridable control table.

    `rows` is `{(table, parameter, season): value}`.
    """
    for (table, parameter, season), value in rows.items():
        master.execute(
            "INSERT OR REPLACE INTO CropManagementParameterOverrides"
            " (idMangt, SeasonOrder, PlantOrder, Model, TargetTable,"
            "  Parameter, Value) VALUES (?, ?, 1, 'dssat', ?, ?, ?)",
            (MANAGEMENT, season, table, parameter, value),
        )
    master.commit()
    resolver = ParameterResolver(dictionary, master)
    resolver.prefetch_management(
        "dssat", dssatxconverter.OVERRIDABLE_TABLES, [MANAGEMENT]
    )
    return resolver


# --- the five tables ------------------------------------------------------


def test_all_five_control_blocks_are_overridable():
    """Not the methods alone: GENERAL, OPTIONS, MANAGEMENT and OUTPUTS too."""
    assert set(dssatxconverter.OVERRIDABLE_TABLES) == {
        "dssat_x_simulation_general",
        "dssat_x_simulation_option",
        "dssat_x_simulation_method",
        "dssat_x_simulation_management",
        "dssat_x_simulation_outputs",
    }


def test_each_table_is_resolved_separately(connections):
    master, dictionary = connections
    resolver = resolver_with(master, dictionary, {
        ("dssat_x_simulation_method", "MEPHO", 2): "L",
        ("dssat_x_simulation_management", "IHARI", 2): "M",
    })

    resolved = dssatxconverter.simulation_overrides(resolver, MANAGEMENT, 2, 1)

    assert resolved["dssat_x_simulation_method"]["mepho"] == "L"
    assert resolved["dssat_x_simulation_management"]["ihari"] == "M"


def test_an_override_of_one_table_does_not_reach_another(connections):
    """`LNSIM` numbers every sub-block, so a per-table resolution is what
    keeps an override of one from renumbering the others."""
    master, dictionary = connections
    resolver = resolver_with(master, dictionary, {
        ("dssat_x_simulation_method", "LNSIM", 1): "7",
    })

    resolved = dssatxconverter.simulation_overrides(resolver, MANAGEMENT, 1, 1)

    assert resolved["dssat_x_simulation_method"]["lnsim"] == "7"
    assert resolved["dssat_x_simulation_management"]["lnsim"] != "7"


# --- harvest at maturity --------------------------------------------------


def management_line(dictionary, overrides):
    block = dssatxconverter.writeBlockManagement(
        "dssat_x_simulation_management", "dssat_x_exp_id", "sim",
        dictionary, overrides,
    )
    return next(line for line in block.splitlines() if " MA " in line)


def test_the_reported_harvest_date_is_the_default(connections):
    _, dictionary = connections

    assert management_line(dictionary, None).split()[-1] == "R"


def test_a_season_can_ask_to_be_harvested_at_maturity(connections):
    """`HARVS = M` ends the run at MDATE (AUTHAR.for:151), which is the
    equivalent of STICS's codrecolte = 1."""
    master, dictionary = connections
    resolver = resolver_with(master, dictionary, {
        ("dssat_x_simulation_management", "IHARI", 2): "M",
    })
    overrides = dssatxconverter.simulation_overrides(
        resolver, MANAGEMENT, 2, 1
    )["dssat_x_simulation_management"]

    assert management_line(dictionary, overrides).split()[-1] == "M"


def test_the_other_seasons_keep_the_reported_date(connections):
    """The override is per crop-season, so season 2 asking for maturity
    leaves seasons 1 and 3 alone."""
    master, dictionary = connections
    resolver = resolver_with(master, dictionary, {
        ("dssat_x_simulation_management", "IHARI", 2): "M",
    })

    for season, expected in ((1, "R"), (2, "M"), (3, "R")):
        overrides = dssatxconverter.simulation_overrides(
            resolver, MANAGEMENT, season, 1
        )["dssat_x_simulation_management"]
        assert management_line(dictionary, overrides).split()[-1] == expected


def test_the_irrigation_and_fertiliser_switches_are_reachable(connections):
    """The TODO comments beside IIRRI and IFERI asked whether these should
    come from the database. Through an override, they now can."""
    master, dictionary = connections
    resolver = resolver_with(master, dictionary, {
        ("dssat_x_simulation_management", "IIRRI", 1): "A",
        ("dssat_x_simulation_management", "IFERI", 1): "A",
    })
    overrides = dssatxconverter.simulation_overrides(
        resolver, MANAGEMENT, 1, 1
    )["dssat_x_simulation_management"]

    fields = management_line(dictionary, overrides).split()
    assert fields[3] == "A"  # IRRIG
    assert fields[4] == "A"  # FERTI
