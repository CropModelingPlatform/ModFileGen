"""The ``agriscale`` command line, and the engine report behind it.

The report exists to answer one question for someone on a locked-down
machine: is my engine found? It has to tell apart "ModFileGen cannot see it"
from "the install itself is incomplete", because the two need different
answers.
"""

import io
import json
import os

import pytest

from modfilegen import GlobalVariables, cli, engines


@pytest.fixture
def global_variables():
    """``GlobalVariables`` restored after the test."""
    snapshot = dict(GlobalVariables)
    try:
        yield GlobalVariables
    finally:
        GlobalVariables.clear()
        GlobalVariables.update(snapshot)


@pytest.fixture
def bare_machine(monkeypatch, tmp_path, global_variables):
    """No engine anywhere: empty PATH, no overrides, an empty portable root."""
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(engines, "PORTABLE_ROOT", tmp_path / "engines")

    # Replacements, not mutations: the Engine objects are module-level and
    # shared, so editing them in place would leak into every later test and
    # monkeypatch would not undo it.
    replacements = {}
    for name, engine in engines.ENGINES.items():
        monkeypatch.delenv(engine.env_var, raising=False)
        if engine.config_key in GlobalVariables:
            global_variables[engine.config_key] = ""
        replacements[name] = engines.Engine(
            label=engine.label,
            config_key=engine.config_key,
            env_var=engine.env_var,
            commands=engine.commands,
            # Drop the absolute install locations: this machine carries the
            # container layout, and the point is to simulate one that does not.
            locations=tuple(
                location
                for location in engine.locations
                if not os.path.isabs(location)
            ),
            companions=engine.companions,
        )
    monkeypatch.setattr(engines, "ENGINES", replacements)
    return tmp_path


def executable(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


# --- inspect ---------------------------------------------------------------


def test_a_missing_engine_is_reported_as_missing(bare_machine):
    finding = engines.inspect("dssat_v47")

    assert finding["status"] == "missing"
    assert finding["origin"] == "not found"


def test_a_complete_install_is_ok(bare_machine, global_variables):
    install = bare_machine / "dssat47"
    executable(install / "dscsm047")
    (install / "DSSATPRO.v47").write_text("data\n")
    global_variables["dssatExecutable"] = str(install / "dscsm047")

    assert engines.inspect("dssat_v47")["status"] == "ok"


def test_a_lone_binary_is_reported_as_incomplete(bare_machine, global_variables):
    """Copying DSCSM047.EXE on its own is the mistake this catches."""
    install = bare_machine / "elsewhere"
    global_variables["dssatExecutable"] = str(executable(install / "dscsm047"))

    finding = engines.inspect("dssat_v47")

    assert finding["status"] == "incomplete"
    assert finding["missing_companions"] == ["DSSATPRO.*"]


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_companions_are_looked_for_beside_the_real_file(
    bare_machine, global_variables
):
    """/usr/bin/dssat is a link into /usr/share/dssat, where DSSATPRO lives."""
    install = bare_machine / "share" / "dssat"
    executable(install / "dscsm047")
    (install / "DSSATPRO.v47").write_text("data\n")
    link_dir = bare_machine / "bin"
    link_dir.mkdir(parents=True)
    link = link_dir / "dssat"
    link.symlink_to(install / "dscsm047")
    global_variables["dssatExecutable"] = str(link)

    finding = engines.inspect("dssat_v47")

    assert finding["status"] == "ok"
    assert finding["executable"] == str(link)


def test_the_origin_names_the_link_of_the_cascade(bare_machine, global_variables):
    install = bare_machine / "sticsv11" / "bin"
    global_variables["sticsV11Executable"] = str(executable(install / "stics_modulo"))

    assert "sticsV11Executable" in engines.inspect("stics_v11")["origin"]


def test_an_engine_without_companions_needs_none(bare_machine, global_variables):
    """STICS is statically linked; only DSSAT, APSIM and CELSIUS have siblings."""
    install = bare_machine / "sticsv11" / "bin"
    global_variables["sticsV11Executable"] = str(executable(install / "stics_modulo"))

    assert engines.inspect("stics_v11")["status"] == "ok"


# --- the command -----------------------------------------------------------


def test_the_report_lists_every_engine(bare_machine):
    stream = io.StringIO()

    cli.engines_report(stream=stream)

    output = stream.getvalue()
    for engine in engines.ENGINES.values():
        assert engine.label in output


def test_a_missing_engine_gets_actionable_guidance(bare_machine):
    stream = io.StringIO()

    cli.engines_report(stream=stream)

    output = stream.getvalue()
    assert "dssatExecutable" in output
    assert "MODFILEGEN_DSSAT_V47" in output


def test_an_incomplete_install_says_so_rather_than_missing(
    bare_machine, global_variables
):
    install = bare_machine / "elsewhere"
    global_variables["dssatExecutable"] = str(executable(install / "dscsm047"))
    stream = io.StringIO()

    cli.engines_report(stream=stream)

    output = stream.getvalue()
    assert "incomplete" in output
    assert "DSSATPRO.*" in output


def test_json_output_is_machine_readable(bare_machine):
    stream = io.StringIO()

    cli.engines_report(stream=stream, as_json=True)

    findings = json.loads(stream.getvalue())
    assert {finding["engine"] for finding in findings} == set(engines.ENGINES)
    assert {"status", "executable", "origin"} <= set(findings[0])


def test_missing_engines_are_not_an_error(bare_machine):
    """Generating input files needs no engine, so this must not fail a build."""
    assert cli.engines_report(stream=io.StringIO()) == 0


def test_the_command_runs_end_to_end(capsys):
    assert cli.main(["engines"]) == 0
    assert "Engine" in capsys.readouterr().out


def test_no_command_shows_the_help(capsys):
    assert cli.main([]) == 1
    assert "agriscale" in capsys.readouterr().out
