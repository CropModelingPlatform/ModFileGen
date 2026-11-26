"""Locating each model's executable, on any OS.

The cascade is GlobalVariables, then the environment variable, then PATH,
then the known install locations, then the bare command name.
"""

import os

import pytest

from modfilegen import GlobalVariables, engines


@pytest.fixture
def global_variables():
    """``GlobalVariables`` restored after the test.

    Defined here rather than taken from conftest so this module stands on its
    own: it is a module-level dict, and a test that writes to it would
    otherwise leak its configuration into the rest of the session.
    """
    snapshot = dict(GlobalVariables)
    try:
        yield GlobalVariables
    finally:
        GlobalVariables.clear()
        GlobalVariables.update(snapshot)


@pytest.fixture
def empty_path(monkeypatch):
    """No engine on PATH and no environment override, for a clean cascade."""
    monkeypatch.setenv("PATH", "")
    for engine in engines.ENGINES.values():
        monkeypatch.delenv(engine.env_var, raising=False)


@pytest.fixture
def portable_root(tmp_path, monkeypatch):
    """A stand-in for ~/.modfilegen/engines."""
    root = tmp_path / "engines"
    monkeypatch.setattr(engines, "PORTABLE_ROOT", root)
    return root


def executable(path, content="#!/bin/sh\nexit 0\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(0o755)
    return path


def on_path(directory, name):
    """A fake engine that ``shutil.which`` will actually find.

    On Windows PATH lookup only accepts the PATHEXT suffixes, so a file with
    no extension is invisible to ``shutil.which`` there. The candidate paths
    are a different matter: an extension-less file still exists on disk, so
    the location tests below need no such treatment.
    """
    suffix = ".bat" if os.name == "nt" else ""
    return executable(directory / (name + suffix))


def test_every_engine_has_a_distinct_configuration_key():
    keys = [engine.config_key for engine in engines.ENGINES.values()]
    variables = [engine.env_var for engine in engines.ENGINES.values()]

    assert len(keys) == len(set(keys))
    assert len(variables) == len(set(variables))


def test_the_configuration_keys_exist_in_global_variables():
    """A key absent from the defaults would never be documented or found."""
    # apsim_path keeps its historical name and its None default.
    keys = {
        engine.config_key
        for engine in engines.ENGINES.values()
        if engine.config_key != "apsim_path"
    }

    assert keys <= set(GlobalVariables)


# --- the cascade, in order ------------------------------------------------


def test_global_variables_wins(global_variables, empty_path, tmp_path):
    target = executable(tmp_path / "chosen")
    global_variables["sticsV11Executable"] = str(target)

    assert engines.resolve("stics_v11") == str(target)


def test_the_environment_variable_is_used_when_nothing_is_configured(
    global_variables, empty_path, monkeypatch, tmp_path
):
    target = executable(tmp_path / "from_env")
    global_variables["sticsV11Executable"] = ""
    monkeypatch.setenv("MODFILEGEN_STICS_V11", str(target))

    assert engines.resolve("stics_v11") == str(target)


def test_global_variables_takes_precedence_over_the_environment(
    global_variables, empty_path, monkeypatch, tmp_path
):
    configured = executable(tmp_path / "configured")
    monkeypatch.setenv("MODFILEGEN_STICS_V11", str(executable(tmp_path / "env")))
    global_variables["sticsV11Executable"] = str(configured)

    assert engines.resolve("stics_v11") == str(configured)


def test_path_is_searched_for_engines_with_a_unique_name(
    global_variables, empty_path, monkeypatch, tmp_path
):
    bindir = tmp_path / "bin"
    target = on_path(bindir, "dssat")
    global_variables["dssatExecutable"] = ""
    monkeypatch.setenv("PATH", str(bindir))

    assert engines.resolve("dssat_v47") == str(target)


def test_stics_is_never_taken_from_path(
    global_variables, empty_path, portable_root, monkeypatch, tmp_path
):
    """v9 and v11 ship the same stics_modulo name.

    Trusting PATH would silently run the wrong model version, so STICS is
    resolved by version-specific location only.
    """
    bindir = tmp_path / "bin"
    on_path(bindir, "stics_modulo")
    monkeypatch.setenv("PATH", str(bindir))
    global_variables["sticsV9Executable"] = ""
    global_variables["sticsV11Executable"] = ""

    assert engines.resolve("stics_v9") != str(bindir / "stics_modulo")
    assert engines.resolve("stics_v11") != str(bindir / "stics_modulo")


def test_a_portable_install_is_found_without_configuration(
    global_variables, empty_path, portable_root
):
    """What an install into ~/.modfilegen/engines gives, with no admin rights."""
    target = executable(portable_root / "sticsv11" / "bin" / "stics_modulo")
    global_variables["sticsV11Executable"] = ""

    assert engines.resolve("stics_v11") == str(target)


def test_the_two_stics_versions_resolve_separately(
    global_variables, empty_path, portable_root
):
    nine = executable(portable_root / "sticsv9" / "bin" / "stics_modulo")
    eleven = executable(portable_root / "sticsv11" / "bin" / "stics_modulo")
    global_variables["sticsV9Executable"] = ""
    global_variables["sticsV11Executable"] = ""

    assert engines.resolve("stics_v9") == str(nine)
    assert engines.resolve("stics_v11") == str(eleven)


def test_nothing_found_falls_back_to_the_command_name(
    global_variables, empty_path, portable_root, monkeypatch
):
    """Resolution never raises: the run fails where the model reports it.

    A made-up engine is used, because the real ones do resolve on a machine
    that has them installed.
    """
    monkeypatch.setitem(
        engines.ENGINES,
        "nowhere",
        engines.Engine(
            label="Nowhere",
            config_key="nowhereExecutable",
            env_var="MODFILEGEN_NOWHERE",
            commands=("nowhere-engine",),
            locations=("nowhere/engine", "/does/not/exist/engine"),
        ),
    )

    assert engines.resolve("nowhere") == "nowhere-engine"


# --- explicit values ------------------------------------------------------


def test_an_explicit_full_path_is_used_as_given(global_variables, empty_path):
    """A Windows path on a POSIX host is still handed through untouched."""
    global_variables["sticsV11Executable"] = r"C:\JavaSTICS\bin\stics_modulo.exe"

    assert engines.resolve("stics_v11") == r"C:\JavaSTICS\bin\stics_modulo.exe"


def test_an_explicit_bare_name_goes_through_path(
    global_variables, empty_path, monkeypatch, tmp_path
):
    """So a configured "Models" becomes Models.exe on Windows."""
    bindir = tmp_path / "bin"
    target = on_path(bindir, "Models")
    monkeypatch.setenv("PATH", str(bindir))

    assert engines.resolve("apsim", configured="Models") == str(target)


# --- guidance -------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(engines.ENGINES))
def test_the_guidance_names_the_key_and_the_variable(name):
    engine = engines.ENGINES[name]

    message = engines.describe(name)

    assert engine.config_key in message
    assert engine.env_var in message


@pytest.mark.parametrize("name", sorted(engines.ENGINES))
def test_not_found_is_a_file_error_that_says_what_to_do(name):
    error = engines.not_found(name, "whatever")

    assert isinstance(error, FileNotFoundError)
    assert engines.ENGINES[name].label in str(error)
    assert engines.ENGINES[name].config_key in str(error)


def test_windows_also_tries_the_exe_suffix(monkeypatch, portable_root):
    """On Windows every candidate is tried with .exe appended."""
    monkeypatch.setattr(engines, "_WINDOWS", True)
    engine = engines.ENGINES["stics_v11"]

    names = [candidate.name for candidate in engine.candidates()]

    assert "stics_modulo" in names
    assert "stics_modulo.exe" in names


def test_posix_does_not_invent_an_exe_suffix(monkeypatch):
    monkeypatch.setattr(engines, "_WINDOWS", False)
    engine = engines.ENGINES["stics_v11"]

    names = [candidate.name for candidate in engine.candidates()]

    assert not any(name.endswith(".exe") for name in names)


def test_a_relative_location_is_taken_under_the_portable_root(portable_root):
    engine = engines.ENGINES["dssat_v47"]

    candidates = [str(candidate) for candidate in engine.candidates()]

    assert str(portable_root / "dssat47" / "dscsm047") in candidates
    assert any(os.path.isabs(candidate) for candidate in candidates)
