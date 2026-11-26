"""Configuring and starting a model run from the command line.

The notebooks were the only way to start a model: paths edited by hand in a
cell, success reported by printing, and no exit status for anything to act
on. These tests cover the translation from options to ``GlobalVariables``,
and the exit status, without running an engine.
"""

import hashlib
import io
import os

import pytest

from modfilegen import GlobalVariables, cli, engines, run_command


@pytest.fixture
def global_variables():
    snapshot = dict(GlobalVariables)
    try:
        yield GlobalVariables
    finally:
        GlobalVariables.clear()
        GlobalVariables.update(snapshot)


@pytest.fixture
def inputs(tmp_path):
    """The files every run needs, so only the option under test varies."""
    master = tmp_path / "MasterInput.db"
    master.write_bytes(b"")
    dictionary = tmp_path / "ModelsDictionary.db"
    dictionary.write_bytes(b"")
    cultivars = tmp_path / "cultivars"
    cultivars.mkdir()
    return {
        "master_input": str(master),
        "models_dictionary": str(dictionary),
        "cultivars": str(cultivars),
        "out": str(tmp_path / "out"),
    }


def options(inputs, **overrides):
    """The parsed arguments, built through the real parser.

    Going through the parser rather than a stub keeps the tests honest about
    option names and defaults.
    """
    argv = ["run", "--model", overrides.pop("model", "stics")]
    for name, value in list(overrides.items()):
        if value is True:
            argv.append(f"--{name.replace('_', '-')}")
            overrides.pop(name)
        elif value is None:
            overrides.pop(name)
    for name, value in overrides.items():
        argv += [f"--{name.replace('_', '-')}", str(value)]
    for name in ("master_input", "models_dictionary", "out", "cultivars"):
        if name not in overrides and name in inputs:
            argv += [f"--{name.replace('_', '-')}", inputs[name]]
    return cli.build_parser().parse_args(argv)


# --- settings --------------------------------------------------------------


def test_the_databases_and_the_output_reach_global_variables(inputs):
    values = run_command.settings(options(inputs, version="v11"))

    assert values["dbMasterInput"] == inputs["master_input"]
    assert values["dbModelsDictionary"] == inputs["models_dictionary"]
    assert values["directorypath"] == inputs["out"]
    assert values["pltfolder"] == inputs["cultivars"]


def test_the_version_and_the_mode_use_each_model_s_own_keys(inputs):
    stics = run_command.settings(options(inputs, version="v11", mode="successive"))
    dssat = run_command.settings(
        options(inputs, model="dssat", version="v48", mode="standard")
    )

    assert stics["stics_version"] == "v11"
    assert stics["stics_mode"] == "successive"
    assert dssat["dssat_version"] == "v48"
    assert dssat["dssat_mode"] == "standard"


def test_an_unknown_version_is_refused_by_name(inputs):
    with pytest.raises(run_command.Problem, match="no version 'v12'"):
        run_command.settings(options(inputs, version="v12"))


def test_a_mode_the_model_does_not_have_is_refused(inputs):
    """APSIM has no successive mode; saying so beats a converter traceback."""
    with pytest.raises(run_command.Problem, match="successive"):
        run_command.settings(
            options(inputs, model="apsim", mode="successive", cultivars=None)
        )


def test_a_missing_database_is_named(inputs, tmp_path):
    inputs["master_input"] = str(tmp_path / "absent.db")

    with pytest.raises(run_command.Problem, match="absent.db"):
        run_command.settings(options(inputs, version="v11"))


def test_stics_without_cultivars_says_what_the_folder_holds(inputs):
    inputs.pop("cultivars")

    with pytest.raises(run_command.Problem, match="plant and genotype files"):
        run_command.settings(options(inputs, version="v11"))


def test_the_executable_lands_on_the_key_for_that_version(inputs, tmp_path):
    engine = tmp_path / "stics_modulo"
    engine.write_text("#!/bin/sh\nexit 0\n")

    values = run_command.settings(
        options(inputs, version="v9", executable=str(engine))
    )

    assert values["sticsV9Executable"] == str(engine)
    assert "sticsV11Executable" not in values


def test_the_intermediate_files_are_kept_by_default(inputs):
    """On a first run they are the only evidence of what the engine got."""
    assert run_command.settings(options(inputs, version="v11"))["dt"] == 0
    assert (
        run_command.settings(
            options(inputs, version="v11", delete_intermediate=True)
        )["dt"]
        == 1
    )


def test_the_scratch_directory_defaults_under_the_output(inputs):
    values = run_command.settings(options(inputs, version="v11"))

    assert values["tempDir"] == os.path.join(inputs["out"], "temp")


def test_stics_gets_a_package_path_the_caller_need_not_know(inputs):
    """It only carries optional overrides, so it is derived, not asked for."""
    values = run_command.settings(options(inputs, version="v11"))

    assert os.path.isdir(values["package"])


# --- manifest --------------------------------------------------------------


def test_the_manifest_lists_every_file_with_its_digest(tmp_path):
    (tmp_path / "a.txt").write_text("one")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("two")

    rows = run_command.manifest(tmp_path)

    assert [name for name, _ in rows] == ["a.txt", "sub/b.txt"]
    assert rows[0][1] == hashlib.sha256(b"one").hexdigest()


def test_the_manifest_uses_forward_slashes_everywhere(tmp_path):
    """A Windows manifest has to compare with a Linux one, byte for byte."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("two")

    assert run_command.manifest(tmp_path)[0][0] == "sub/b.txt"
    assert "\\" not in run_command.manifest(tmp_path)[0][0]


def test_the_scratch_directory_is_left_out(tmp_path):
    """Engine scratch carries run timestamps, which would differ every time."""
    (tmp_path / "keep.txt").write_text("keep")
    scratch = tmp_path / "temp"
    scratch.mkdir()
    (scratch / "noise.txt").write_text("noise")

    rows = run_command.manifest(tmp_path, skip=[scratch])

    assert [name for name, _ in rows] == ["keep.txt"]


def test_the_manifest_is_written_in_sha256sum_order(tmp_path):
    destination = tmp_path / "out.sha256"

    run_command.write_manifest(destination, [("b.txt", "ff"), ("a.txt", "ee")])

    assert destination.read_text(encoding="utf-8") == "ff  b.txt\nee  a.txt\n"


# --- perform ---------------------------------------------------------------


@pytest.fixture
def engine_is_ready(monkeypatch):
    monkeypatch.setattr(
        engines,
        "inspect",
        lambda name, configured=None: {
            "engine": name,
            "label": engines.ENGINES[name].label,
            "executable": "/somewhere/engine",
            "origin": "given",
            "status": "ok",
            "missing_companions": [],
        },
    )


@pytest.fixture
def dispatcher(monkeypatch):
    """Replaces run_stics, so nothing generates files or starts an engine."""
    from modfilegen import Converter

    calls = []
    monkeypatch.setattr(Converter, "run_stics", lambda: calls.append("ran"))
    return calls


def test_a_successful_run_reports_zero(
    inputs, engine_is_ready, dispatcher, global_variables
):
    status = run_command.perform(options(inputs, version="v11"), io.StringIO())

    assert status == 0
    assert dispatcher == ["ran"]


def test_the_run_configures_global_variables_before_dispatching(
    inputs, engine_is_ready, dispatcher, global_variables
):
    run_command.perform(options(inputs, version="v11"), io.StringIO())

    assert GlobalVariables["stics_version"] == "v11"
    assert GlobalVariables["directorypath"] == inputs["out"]


def test_a_missing_engine_stops_before_any_work(
    inputs, monkeypatch, dispatcher, global_variables
):
    """Generating the inputs takes real time; failing after it over a path
    that was wrong from the start is a poor trade."""
    monkeypatch.setattr(
        engines,
        "inspect",
        lambda name, configured=None: {
            "engine": name,
            "label": "STICS v11",
            "executable": "stics_modulo",
            "origin": "not found",
            "status": "missing",
            "missing_companions": [],
        },
    )
    stream = io.StringIO()

    status = run_command.perform(options(inputs, version="v11"), stream)

    assert status == 1
    assert dispatcher == []
    assert "MODFILEGEN_STICS_V11" in stream.getvalue()


def test_a_failing_run_reports_one_and_says_where_to_look(
    inputs, engine_is_ready, monkeypatch, global_variables
):
    from modfilegen import Converter

    def explode():
        scratch = os.path.join(inputs["out"], "temp")
        with open(os.path.join(scratch, "evidence.txt"), "w") as stream:
            stream.write("what the engine was given\n")
        raise RuntimeError("the engine refused the inputs")

    monkeypatch.setattr(Converter, "run_stics", explode)
    stream = io.StringIO()

    status = run_command.perform(options(inputs, version="v11"), stream)

    assert status == 1
    assert "the engine refused the inputs" in stream.getvalue()
    assert "are kept in" in stream.getvalue()


def test_no_manifest_is_written_for_a_failed_run(
    inputs, engine_is_ready, monkeypatch, tmp_path, global_variables
):
    from modfilegen import Converter

    monkeypatch.setattr(Converter, "run_stics", lambda: 1 / 0)
    destination = tmp_path / "run.sha256"

    run_command.perform(
        options(inputs, version="v11", manifest=str(destination)), io.StringIO()
    )

    assert not destination.exists()


def test_the_manifest_is_written_after_a_successful_run(
    inputs, engine_is_ready, monkeypatch, tmp_path, global_variables
):
    from modfilegen import Converter

    def produce():
        with open(os.path.join(inputs["out"], "summary.csv"), "w") as stream:
            stream.write("idsim\n")

    monkeypatch.setattr(Converter, "run_stics", produce)
    destination = tmp_path / "run.sha256"

    status = run_command.perform(
        options(inputs, version="v11", manifest=str(destination)), io.StringIO()
    )

    assert status == 0
    assert "summary.csv" in destination.read_text(encoding="utf-8")


def test_a_misconfiguration_is_a_usage_error(inputs, tmp_path):
    """Exit 2, as argparse uses, so a script can tell it from a failed run."""
    inputs["master_input"] = str(tmp_path / "absent.db")

    status = run_command.perform(options(inputs, version="v11"), io.StringIO())

    assert status == 2


def test_the_command_reaches_perform_through_main(
    inputs, engine_is_ready, dispatcher, global_variables
):
    arguments = [
        "run", "--model", "stics", "--version", "v11",
        "--master-input", inputs["master_input"],
        "--models-dictionary", inputs["models_dictionary"],
        "--cultivars", inputs["cultivars"],
        "--out", inputs["out"],
    ]

    assert cli.main(arguments) == 0
    assert dispatcher == ["ran"]


# --- comparable names ------------------------------------------------------


def test_a_run_identifier_is_replaced_in_the_manifest():
    """Every model names its summary CSV <uuid4>_<model>.csv, so two runs of
    the same inputs would otherwise share no single line."""
    name = "f18b1399-1c98-41c7-9974-4974544c94f9_stics_successive.csv"

    assert run_command.comparable_name(name) == "<run-id>_stics_successive.csv"


def test_only_a_leading_identifier_is_replaced():
    assert (
        run_command.comparable_name("sub/f18b1399-1c98-41c7-9974-4974544c94f9_a.csv")
        == "sub/<run-id>_a.csv"
    )
    assert run_command.comparable_name("plain.csv") == "plain.csv"
    assert (
        run_command.comparable_name("a_f18b1399-1c98-41c7-9974-4974544c94f9.csv")
        == "a_f18b1399-1c98-41c7-9974-4974544c94f9.csv"
    )


def test_two_runs_of_the_same_inputs_give_the_same_manifest(tmp_path):
    first, second = tmp_path / "one", tmp_path / "two"
    for directory, identifier in (
        (first, "f18b1399-1c98-41c7-9974-4974544c94f9"),
        (second, "0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9"),
    ):
        directory.mkdir()
        (directory / f"{identifier}_stics.csv").write_text("idsim,yield\na,1\n")

    assert run_command.manifest(first) == run_command.manifest(second)


# --- the accounting --------------------------------------------------------


def test_a_model_without_a_survey_is_not_counted(inputs):
    """STICS declines nothing, so there is nothing to reconcile."""
    assert run_command.MODELS["stics"].survey is None
    assert (
        run_command.crop_seasons(inputs["master_input"], run_command.MODELS["stics"],
                                 "standard")
        is None
    )


def test_the_survey_is_reported_before_the_run(tmp_path):
    stream = io.StringIO()

    run_command.report_the_survey(
        {"requested": 10, "applicable": 1, "declined": {"an association": 6,
                                                        "a rotation": 3}},
        stream,
    )

    output = stream.getvalue()
    assert "10 crop-seasons requested" in output
    assert "6 declined: an association" in output
    assert "3 declined: a rotation" in output
    assert "1 to simulate" in output


def test_the_produced_rows_are_counted_from_the_summary(tmp_path):
    (tmp_path / "abc_dssat.csv").write_text("IdSim,Yield\na,1\nb,2\n")

    assert run_command.count_produced(tmp_path, "dssat") == 2


def test_an_intermediate_chunk_is_not_mistaken_for_the_summary(tmp_path):
    """DSSAT leaves chunk_0.csv in the output directory."""
    (tmp_path / "abc_dssat.csv").write_text("IdSim\na\n")
    (tmp_path / "chunk_0.csv").write_text("IdSim\na\nb\nc\n")

    assert run_command.count_produced(tmp_path, "dssat") == 1


def test_an_uncountable_output_is_admitted_not_guessed(tmp_path):
    """A wrong count would fail a good run, which is worse than not checking."""
    assert run_command.count_produced(tmp_path, "dssat") is None

    (tmp_path / "a_dssat.csv").write_text("IdSim\na\n")
    (tmp_path / "b_dssat.csv").write_text("IdSim\nb\n")
    assert run_command.count_produced(tmp_path, "dssat") is None


def test_a_run_short_of_its_applicable_work_fails(
    inputs, engine_is_ready, monkeypatch, global_variables
):
    """The point of the whole exercise: a defect must not look like a
    declined simulation."""
    from modfilegen import Converter

    monkeypatch.setattr(
        run_command, "crop_seasons",
        lambda database, model, mode: {
            "requested": 10, "applicable": 3, "declined": {"an association": 7},
        },
    )

    def produce_too_little():
        with open(os.path.join(inputs["out"], "x_dssat.csv"), "w") as stream:
            stream.write("IdSim\na\n")

    monkeypatch.setattr(Converter, "run_dssat", produce_too_little)
    stream = io.StringIO()

    status = run_command.perform(
        options(inputs, model="dssat", version="v48"), stream
    )

    assert status == 1
    assert "1 of 3 crop-seasons were produced" in stream.getvalue()


def test_a_run_that_produced_its_applicable_work_passes(
    inputs, engine_is_ready, monkeypatch, global_variables
):
    from modfilegen import Converter

    monkeypatch.setattr(
        run_command, "crop_seasons",
        lambda database, model, mode: {
            "requested": 10, "applicable": 1, "declined": {"an association": 9},
        },
    )

    def produce():
        with open(os.path.join(inputs["out"], "x_dssat.csv"), "w") as stream:
            stream.write("IdSim\na\n")

    monkeypatch.setattr(Converter, "run_dssat", produce)
    stream = io.StringIO()

    status = run_command.perform(
        options(inputs, model="dssat", version="v48"), stream
    )

    assert status == 0
    assert "1 crop-seasons produced" in stream.getvalue()
