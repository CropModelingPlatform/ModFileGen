import sqlite3
import pytest

from modfilegen.parameter_resolver import ParameterResolver


def test_prefetch_merges_defaults_and_soil_overrides():
    model_dictionary = sqlite3.connect(":memory:")
    model_dictionary.execute(
        """
        CREATE TABLE Variables (
            model TEXT, [Table] TEXT, Champ TEXT, Type TEXT,
            Minnval REAL, Maxval REAL,
            Default_Value_Datamill TEXT,
            defaultValueOtherSource TEXT
        )
        """
    )
    model_dictionary.executemany(
        "INSERT INTO Variables VALUES ('sticsv11', 'paramsol', ?, 'real', NULL, NULL, ?, ?)",
        [
            ("profhum", "30", None),
            ("ksol", "5", "6"),
        ],
    )

    master_input = sqlite3.connect(":memory:")
    master_input.execute(
        """
        CREATE TABLE SoilParameterOverrides (
            IdSoil TEXT, Model TEXT, TargetTable TEXT,
            Parameter TEXT, Value TEXT
        )
        """
    )
    master_input.execute(
        "INSERT INTO SoilParameterOverrides VALUES ('Soil-1', 'sticsv11', 'paramsol', 'profhum', '42')"
    )

    resolver = ParameterResolver(model_dictionary, master_input)
    resolver.prefetch("sticsv11", {"paramsol"}, {"soil-1", "soil-2"})

    soil_1 = resolver.resolve("STICSV11", "PARAMSOL", "SOIL-1")
    soil_2 = resolver.resolve("sticsv11", "paramsol", "soil-2")

    assert dict(soil_1) == {"profhum": 42.0, "ksol": 6.0}
    assert dict(soil_2) == {"profhum": 30.0, "ksol": 6.0}
    assert resolver.has_override("sticsv11", "paramsol", "profhum", "soil-1")
    assert not resolver.has_override("sticsv11", "paramsol", "ksol", "soil-1")


def test_soil_defaults_work_without_override_table():
    model_dictionary = sqlite3.connect(":memory:")
    model_dictionary.execute(
        """
        CREATE TABLE Variables (
            model TEXT, [Table] TEXT, Champ TEXT, Type TEXT,
            Minnval REAL, Maxval REAL,
            Default_Value_Datamill TEXT,
            defaultValueOtherSource TEXT
        )
        """
    )
    model_dictionary.execute(
        "INSERT INTO Variables VALUES "
        "('celsius', 'Soil', 'Zsurf', 'real', NULL, NULL, '50', NULL)"
    )

    resolver = ParameterResolver(
        model_dictionary, sqlite3.connect(":memory:")
    )
    resolver.prefetch("celsius", {"Soil"}, {"legacy-soil"})

    assert resolver.resolve("celsius", "Soil", "legacy-soil")["zsurf"] == 50.0


def test_resolve_uses_prefetched_values_after_database_changes():
    model_dictionary = sqlite3.connect(":memory:")
    model_dictionary.execute(
        """
        CREATE TABLE Variables (
            model TEXT, [Table] TEXT, Champ TEXT, Type TEXT,
            Minnval REAL, Maxval REAL,
            Default_Value_Datamill TEXT,
            defaultValueOtherSource TEXT
        )
        """
    )
    model_dictionary.execute(
        "INSERT INTO Variables VALUES ('sticsv11', 'paramsol', 'ksol', 'real', NULL, NULL, '5', NULL)"
    )
    master_input = sqlite3.connect(":memory:")
    master_input.execute(
        """
        CREATE TABLE SoilParameterOverrides (
            IdSoil TEXT, Model TEXT, TargetTable TEXT,
            Parameter TEXT, Value TEXT
        )
        """
    )

    resolver = ParameterResolver(model_dictionary, master_input)
    resolver.prefetch("sticsv11", {"paramsol"}, {"soil-1"})
    master_input.execute(
        "INSERT INTO SoilParameterOverrides VALUES ('soil-1', 'sticsv11', 'paramsol', 'ksol', '99')"
    )

    assert resolver.resolve("sticsv11", "paramsol", "soil-1")["ksol"] == 5.0


def test_prefetch_merges_defaults_and_crop_management_overrides():
    model_dictionary = sqlite3.connect(":memory:")
    model_dictionary.execute(
        """
        CREATE TABLE Variables (
            model TEXT, [Table] TEXT, Champ TEXT, Type TEXT,
            Minnval REAL, Maxval REAL,
            Default_Value_Datamill TEXT,
            defaultValueOtherSource TEXT
        )
        """
    )
    model_dictionary.executemany(
        "INSERT INTO Variables VALUES "
        "('sticsv11', 'fictec1', ?, ?, NULL, NULL, ?, NULL)",
        [
            ("codecalirrig", "integer", "2"),
            ("ratiol", "real", "0.3"),
        ],
    )
    master_input = sqlite3.connect(":memory:")
    master_input.execute(
        """
        CREATE TABLE CropManagementParameterOverrides (
            idMangt TEXT, SeasonOrder INTEGER, PlantOrder INTEGER,
            Model TEXT, TargetTable TEXT, Parameter TEXT, Value TEXT
        )
        """
    )
    master_input.executemany(
        "INSERT INTO CropManagementParameterOverrides VALUES "
        "('rotation', ?, 1, 'sticsv11', 'fictec1', ?, ?)",
        [
            (2, "codecalirrig", "1"),
            (2, "ratiol", "0.45"),
        ],
    )

    resolver = ParameterResolver(model_dictionary, master_input)
    resolver.prefetch_management("sticsv11", {"fictec1"}, {"ROTATION"})

    season_1 = resolver.resolve_management(
        "sticsv11", "fictec1", "rotation", 1, 1
    )
    season_2 = resolver.resolve_management(
        "sticsv11", "fictec1", "rotation", 2, 1
    )
    assert dict(season_1) == {"codecalirrig": 2, "ratiol": 0.3}
    assert dict(season_2) == {"codecalirrig": 1, "ratiol": 0.45}
    assert resolver.has_management_override(
        "sticsv11", "fictec1", "ratiol", "rotation", 2, 1
    )


def test_management_defaults_work_without_override_table():
    model_dictionary = sqlite3.connect(":memory:")
    model_dictionary.execute(
        """
        CREATE TABLE Variables (
            model TEXT, [Table] TEXT, Champ TEXT, Type TEXT,
            Minnval REAL, Maxval REAL,
            Default_Value_Datamill TEXT,
            defaultValueOtherSource TEXT
        )
        """
    )
    model_dictionary.execute(
        "INSERT INTO Variables VALUES "
        "('sticsv11', 'fictec1', 'codecalirrig', 'integer', "
        "NULL, NULL, '2', NULL)"
    )
    master_input = sqlite3.connect(":memory:")

    resolver = ParameterResolver(model_dictionary, master_input)
    resolver.prefetch_management("sticsv11", {"fictec1"}, {"legacy"})

    assert resolver.resolve_management(
        "sticsv11", "fictec1", "legacy", 1, 1
    )["codecalirrig"] == 2


def test_prefetch_merges_defaults_and_point_overrides():
    model_dictionary = sqlite3.connect(":memory:")
    model_dictionary.execute(
        """
        CREATE TABLE Variables (
            model TEXT, [Table] TEXT, Champ TEXT, Type TEXT,
            Minnval REAL, Maxval REAL,
            Default_Value_Datamill TEXT,
            defaultValueOtherSource TEXT
        )
        """
    )
    model_dictionary.executemany(
        "INSERT INTO Variables VALUES "
        "('sticsv11', 'station', ?, 'real', NULL, NULL, ?, NULL)",
        [("aclim", "20"), ("concrr", "0.02")],
    )
    master_input = sqlite3.connect(":memory:")
    master_input.execute(
        """
        CREATE TABLE PointParameterOverrides (
            idPoint TEXT, Model TEXT, TargetTable TEXT,
            Parameter TEXT, Value TEXT
        )
        """
    )
    master_input.executemany(
        "INSERT INTO PointParameterOverrides VALUES "
        "(?, 'sticsv11', 'station', ?, ?)",
        [("point-a", "aclim", "18"), ("point-a", "concrr", "0.01")],
    )

    resolver = ParameterResolver(model_dictionary, master_input)
    resolver.prefetch_point("sticsv11", {"station"}, {"point-a", "point-b"})

    assert dict(resolver.resolve_point("sticsv11", "station", "POINT-A")) == {
        "aclim": 18.0, "concrr": 0.01,
    }
    assert dict(resolver.resolve_point("sticsv11", "station", "point-b")) == {
        "aclim": 20.0, "concrr": 0.02,
    }
    assert resolver.has_point_override(
        "sticsv11", "station", "aclim", "point-a"
    )


def test_point_defaults_work_without_override_table():
    model_dictionary = sqlite3.connect(":memory:")
    model_dictionary.execute(
        """
        CREATE TABLE Variables (
            model TEXT, [Table] TEXT, Champ TEXT, Type TEXT,
            Minnval REAL, Maxval REAL,
            Default_Value_Datamill TEXT,
            defaultValueOtherSource TEXT
        )
        """
    )
    model_dictionary.execute(
        "INSERT INTO Variables VALUES "
        "('sticsv11', 'station', 'aclim', 'real', NULL, NULL, '20', NULL)"
    )
    resolver = ParameterResolver(
        model_dictionary, sqlite3.connect(":memory:")
    )
    resolver.prefetch_point("sticsv11", {"station"}, {"legacy-point"})

    assert resolver.resolve_point(
        "sticsv11", "station", "legacy-point"
    )["aclim"] == 20.0


def _layer_resolver(overrides, with_num_layer=True):
    model_dictionary = sqlite3.connect(":memory:")
    model_dictionary.execute(
        "CREATE TABLE Variables (model TEXT, [Table] TEXT, Champ TEXT, Type TEXT, "
        "Minnval REAL, Maxval REAL, Default_Value_Datamill TEXT, "
        "defaultValueOtherSource TEXT)"
    )
    model_dictionary.executemany(
        "INSERT INTO Variables VALUES ('sticsv11', 'paramsol', ?, ?, NULL, NULL, ?, NULL)",
        [("infil", "real", "50"), ("epd", "integer", "10"), ("q0", "real", "12")],
    )
    master_input = sqlite3.connect(":memory:")
    layer_column = ", NumLayer INTEGER NOT NULL DEFAULT 0" if with_num_layer else ""
    master_input.execute(
        "CREATE TABLE SoilParameterOverrides (IdSoil TEXT, Model TEXT, "
        f"TargetTable TEXT, Parameter TEXT, Value TEXT{layer_column})"
    )
    columns = "IdSoil, Model, TargetTable, Parameter, Value"
    if with_num_layer:
        columns += ", NumLayer"
    master_input.executemany(
        f"INSERT INTO SoilParameterOverrides ({columns}) "
        f"VALUES ({', '.join('?' for _ in columns.split(','))})",
        overrides,
    )
    resolver = ParameterResolver(model_dictionary, master_input)
    resolver.prefetch("sticsv11", {"paramsol"}, {"soil-1"})
    return resolver


def test_layer_override_then_profile_override_then_default():
    resolver = _layer_resolver([
        ("soil-1", "sticsv11", "paramsol", "infil", "20", 0),
        ("soil-1", "sticsv11", "paramsol", "infil", "5", 2),
        ("soil-1", "sticsv11", "paramsol", "epd", "3", 3),
    ])

    layers = resolver.resolve_layers("sticsv11", "paramsol", "soil-1", 3, ("infil", "epd"))

    assert [dict(layer) for layer in layers] == [
        {"infil": 20.0, "epd": 10},
        {"infil": 5.0, "epd": 10},
        {"infil": 20.0, "epd": 3},
    ]
    # The whole-profile view keeps the NumLayer = 0 values only.
    assert dict(resolver.resolve("sticsv11", "paramsol", "soil-1")) == {
        "infil": 20.0, "epd": 10, "q0": 12.0,
    }


def test_override_on_a_missing_layer_is_an_error():
    resolver = _layer_resolver([("soil-1", "sticsv11", "paramsol", "infil", "5", 3)])

    with pytest.raises(ValueError, match="layer 3 of soil 'soil-1', which has 2"):
        resolver.resolve_layers("sticsv11", "paramsol", "soil-1", 2, ("infil",))


def test_layer_override_on_a_whole_soil_parameter_is_an_error():
    resolver = _layer_resolver([("soil-1", "sticsv11", "paramsol", "q0", "9", 1)])

    with pytest.raises(ValueError, match=r"whole-soil parameter\(s\) \['q0'\]"):
        resolver.resolve_layers("sticsv11", "paramsol", "soil-1", 1, ("infil",))


def test_tables_without_num_layer_hold_whole_profile_values():
    resolver = _layer_resolver(
        [("soil-1", "sticsv11", "paramsol", "infil", "20")], with_num_layer=False
    )

    layers = resolver.resolve_layers("sticsv11", "paramsol", "soil-1", 2, ("infil",))

    assert [dict(layer) for layer in layers] == [{"infil": 20.0}, {"infil": 20.0}]
