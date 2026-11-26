"""The shell-free engine launcher that replaces the ``*run.sh`` scripts.

A stub engine (this interpreter, running a one-liner) stands in for the real
model, so the behaviour the scripts used to provide can be pinned without
installing STICS or DSSAT.
"""

import os
import subprocess
import sys

import pytest

from modfilegen import engine_runner


def stub(code):
    """Arguments running ``code`` in an isolated interpreter.

    ``-I`` keeps the stub from importing anything out of the working
    directory it is pointed at.
    """
    return [sys.executable, ["-I", "-c", code]]


# --- run_engine ------------------------------------------------------------


def test_the_engine_runs_in_the_usm_directory(tmp_path):
    """``cwd`` replaces the ``cd "$USM_DIR"`` of the scripts."""
    usmdir = tmp_path / "usm"
    usmdir.mkdir()
    executable, arguments = stub(
        "import pathlib; pathlib.Path('Summary.OUT').write_text('done')"
    )

    engine_runner.run_engine(executable, arguments, cwd=usmdir, timeout=60)

    assert (usmdir / "Summary.OUT").read_text() == "done"
    assert not (tmp_path / "Summary.OUT").exists()


def test_a_failing_engine_raises_with_its_stderr(tmp_path):
    executable, arguments = stub("import sys; sys.stderr.write('STOP 99\\n'); sys.exit(99)")

    with pytest.raises(subprocess.CalledProcessError) as failure:
        engine_runner.run_engine(executable, arguments, cwd=tmp_path, timeout=60)

    assert failure.value.returncode == 99
    assert "STOP 99" in failure.value.stderr


def test_check_false_returns_the_failure_for_the_caller_to_inspect(tmp_path):
    """DSSAT standard checks the return code and stderr itself."""
    executable, arguments = stub("import sys; sys.stderr.write('STOP 99\\n'); sys.exit(99)")

    result = engine_runner.run_engine(
        executable, arguments, cwd=tmp_path, timeout=60, check=False
    )

    assert result.returncode == 99
    assert "STOP 99" in result.stderr


def test_engine_stdout_is_discarded_by_default(tmp_path):
    """STICS prints a lot; the scripts sent it to /dev/null and so do we."""
    executable, arguments = stub("print('x' * 1000)")

    result = engine_runner.run_engine(executable, arguments, cwd=tmp_path, timeout=60)

    assert result.stdout is None


def test_a_hanging_engine_times_out(tmp_path):
    executable, arguments = stub("import time; time.sleep(30)")

    with pytest.raises(subprocess.TimeoutExpired):
        engine_runner.run_engine(executable, arguments, cwd=tmp_path, timeout=1)


# --- copy_output / copy_outputs -------------------------------------------


def test_copy_output_renames_into_the_destination(tmp_path):
    source = tmp_path / "usm"
    source.mkdir()
    (source / "Summary.OUT").write_text("rows")
    destination = tmp_path / "out"
    destination.mkdir()

    result = engine_runner.copy_output(
        source, "Summary.OUT", destination, "Summary_sim1.OUT"
    )

    assert result == destination / "Summary_sim1.OUT"
    assert result.read_text() == "rows"


def test_copy_output_skips_a_file_the_engine_did_not_write(tmp_path):
    """The scripts guarded every copy with ``[ -f ... ]``."""
    source = tmp_path / "usm"
    source.mkdir()
    destination = tmp_path / "out"
    destination.mkdir()

    assert engine_runner.copy_output(source, "absent.OUT", destination, "x.OUT") is None
    assert list(destination.iterdir()) == []


def test_copy_outputs_renames_every_match(tmp_path):
    """STICS v11 copies all mod_s*.sti, keeping each stem in the name."""
    source = tmp_path / "usm"
    source.mkdir()
    for name in ("mod_sa.sti", "mod_sb.sti", "other.sti"):
        (source / name).write_text(name)
    destination = tmp_path / "out"
    destination.mkdir()

    copied = engine_runner.copy_outputs(
        source,
        "mod_s*.sti",
        destination,
        rename=lambda path: f"mod_s_sim1__{path.stem}.sti",
    )

    assert [path.name for path in copied] == [
        "mod_s_sim1__mod_sa.sti",
        "mod_s_sim1__mod_sb.sti",
    ]
    assert not (destination / "other.sti").exists()


def test_copy_outputs_first_only_takes_the_first_sorted_match(tmp_path):
    """STICS v9 copied the first match and broke out of the loop."""
    source = tmp_path / "usm"
    source.mkdir()
    for name in ("mod_sb.sti", "mod_sa.sti"):
        (source / name).write_text(name)
    destination = tmp_path / "out"
    destination.mkdir()

    copied = engine_runner.copy_outputs(
        source,
        "mod_s*.sti",
        destination,
        rename=lambda path: "mod_s_sim1.sti",
        first_only=True,
    )

    assert [path.name for path in copied] == ["mod_s_sim1.sti"]
    assert copied[0].read_text() == "mod_sa.sti"


def test_copy_outputs_on_no_match_is_not_an_error(tmp_path):
    source = tmp_path / "usm"
    source.mkdir()
    destination = tmp_path / "out"
    destination.mkdir()

    assert engine_runner.copy_outputs(
        source, "mod_s*.sti", destination, rename=lambda path: path.name
    ) == []


# --- removal ---------------------------------------------------------------


def test_remove_tree_deletes_the_usm(tmp_path):
    usmdir = tmp_path / "usm"
    (usmdir / "nested").mkdir(parents=True)
    (usmdir / "nested" / "file.txt").write_text("x")

    assert engine_runner.remove_tree(usmdir) is True
    assert not usmdir.exists()


def test_remove_tree_on_an_absent_directory_succeeds(tmp_path):
    assert engine_runner.remove_tree(tmp_path / "absent") is True


def test_remove_usm_in_the_background_eventually_deletes(tmp_path):
    usmdir = tmp_path / "usm"
    usmdir.mkdir()
    (usmdir / "file.txt").write_text("x")

    assert engine_runner.remove_usm(usmdir) is None
    engine_runner.wait_for_removals()

    assert not usmdir.exists()


def test_remove_usm_can_be_synchronous(tmp_path):
    usmdir = tmp_path / "usm"
    usmdir.mkdir()

    assert engine_runner.remove_usm(usmdir, background=False) is True
    assert not usmdir.exists()


# --- wrapper scripts the OS will not exec itself -------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shebang behaviour")
def test_a_wrapper_without_a_shebang_still_runs(tmp_path):
    """DSSAT's own run_dssat is a one-line script with no shebang.

    ``execve`` returns ENOEXEC on it; bash used to fall back to ``sh``, and
    so must we, or every DSSAT run fails with "Exec format error".
    """
    wrapper = tmp_path / "wrapper"
    wrapper.write_text('echo "$1" > called.txt\n')
    wrapper.chmod(0o755)
    usmdir = tmp_path / "usm"
    usmdir.mkdir()

    result = engine_runner.run_engine(
        wrapper, ["B", "DSSBatch.v47"], cwd=usmdir, timeout=60
    )

    assert result.returncode == 0
    assert (usmdir / "called.txt").read_text().strip() == "B"


def test_a_genuinely_missing_executable_still_raises(tmp_path):
    """The fallback must not mask a wrong path."""
    with pytest.raises(FileNotFoundError):
        engine_runner.run_engine(
            tmp_path / "does_not_exist", cwd=tmp_path, timeout=60
        )


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shebang behaviour")
def test_a_wrapper_named_on_the_path_is_resolved(tmp_path, monkeypatch):
    """The engine is usually a bare name on PATH, like DSSAT's ``dssat``.

    A direct exec looks it up in PATH; an interpreter would take it as a path
    relative to the USM directory and fail with "command not found".
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    wrapper = bindir / "fake-engine"
    wrapper.write_text('echo "$1" > called.txt\n')
    wrapper.chmod(0o755)
    usmdir = tmp_path / "usm"
    usmdir.mkdir()
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])

    result = engine_runner.run_engine(
        "fake-engine", ["B", "DSSBatch.v47"], cwd=usmdir, timeout=60
    )

    assert result.returncode == 0
    assert (usmdir / "called.txt").read_text().strip() == "B"
