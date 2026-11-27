"""Checking an installation that has no engine yet.

A student who has just run ``pip install`` owns no model. The useful check
is therefore the one that needs none: build the packaged fixture, compare it
against a digest shipped beside it, and exercise the behaviour that differed
between Linux and Windows.
"""

import io

import pytest

from modfilegen import fixtures, selftest


# --- the packaged data ----------------------------------------------------


def test_the_fixture_sources_ship_with_the_package():
    """Not under tests/: a wheel carries no test tree."""
    assert (fixtures.SOURCES_DIR / "masterinput" / "schema.sql").is_file()
    assert list((fixtures.SOURCES_DIR / "masterinput").glob("*.csv"))


def test_the_plant_files_ship_too():
    """A run needs them, and a student has no repository to take them from."""
    assert (fixtures.CULTIVARS_DIR / "stics" / "maitest.txt").is_file()
    assert (fixtures.CULTIVARS_DIR / "stics" / "peanut.txt").is_file()
    assert (fixtures.CULTIVARS_DIR / "dssat" / "PNGRO048.CUL").is_file()


def test_the_demo_databases_are_built_where_asked(tmp_path):
    built = fixtures.write_demo(tmp_path)

    assert set(built) == set(fixtures.FIXTURES)
    for path in built.values():
        assert path.is_file() and path.stat().st_size > 0


def test_the_demo_tells_a_reader_what_to_run_next(tmp_path):
    stream = io.StringIO()

    fixtures.write_demo(tmp_path, stream)

    output = stream.getvalue()
    assert "agriscale run --model stics" in output
    assert str(fixtures.CULTIVARS_DIR / "stics") in output


# --- the digests ----------------------------------------------------------


def test_the_built_fixture_matches_its_shipped_digest(tmp_path):
    """The reason the digest exists: a student learns the data arrived
    intact, rather than discovering it later through a wrong result."""
    built = selftest.build_the_fixture(tmp_path)
    expected = selftest.reference_digests()

    assert expected, "the reference digests must ship with the package"
    for name, path in built.items():
        assert selftest.content_digest(path) == expected[name]


def test_the_digest_covers_the_rows_not_the_file(tmp_path):
    """SQLite files are not reproducible -- page order and library version
    show through -- so two builds of the same sources must still agree."""
    first = selftest.build_the_fixture(tmp_path / "one")["masterinput"]
    second = selftest.build_the_fixture(tmp_path / "two")["masterinput"]

    assert first.read_bytes() != second.read_bytes() or True  # may differ
    assert selftest.content_digest(first) == selftest.content_digest(second)


def test_a_changed_row_changes_the_digest(tmp_path):
    import sqlite3

    database = selftest.build_the_fixture(tmp_path)["masterinput"]
    before = selftest.content_digest(database)
    connection = sqlite3.connect(database)
    connection.execute("UPDATE SimUnitList SET StartDay = StartDay + 1")
    connection.commit()
    connection.close()

    assert selftest.content_digest(database) != before


# --- the platform checks --------------------------------------------------


def test_every_platform_check_holds_here(tmp_path):
    for what, reason in selftest.platform_checks(tmp_path):
        assert reason is None, f"{what}: {reason}"


def test_the_checks_cover_what_windows_broke(tmp_path):
    """Each one stands for a defect the cross-platform work fixed."""
    names = [what for what, _ in selftest.platform_checks(tmp_path)]

    assert any("UTF-8" in name for name in names)
    assert any("path" in name for name in names)
    assert any("APSIM" in name for name in names)
    assert any("DSSAT" in name for name in names)


# --- the command ----------------------------------------------------------


def test_a_sound_installation_reports_zero(tmp_path):
    stream = io.StringIO()

    status = selftest.run(stream, tmp_path)

    assert status == 0
    assert "This installation is sound" in stream.getvalue()


def test_a_missing_engine_is_not_a_failure(tmp_path, monkeypatch):
    """Generating input files needs none, and a student checks the install
    before fetching any model."""
    from modfilegen import engines

    monkeypatch.setattr(
        engines, "inspect",
        lambda name, configured=None: {
            "engine": name, "label": name, "executable": name,
            "origin": "not found", "status": "missing",
            "missing_companions": [],
        },
    )
    stream = io.StringIO()

    assert selftest.run(stream, tmp_path) == 0
    assert "missing" in stream.getvalue()


def test_a_fixture_that_does_not_match_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        selftest, "reference_digests", lambda: {"masterinput": "nonsense"}
    )
    stream = io.StringIO()

    status = selftest.run(stream, tmp_path)

    assert status == 1
    assert "DIFFERS" in stream.getvalue()


def test_the_command_reaches_selftest(capsys, tmp_path):
    from modfilegen import cli

    assert cli.main(["selftest", "--out", str(tmp_path)]) == 0
    assert "The packaged fixture" in capsys.readouterr().out


def test_the_fixture_command_builds_them(capsys, tmp_path):
    from modfilegen import cli

    assert cli.main(["fixture", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "masterinput.db").is_file()
    assert "agriscale run" in capsys.readouterr().out
