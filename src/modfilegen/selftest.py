"""Check an installation without needing a model engine.

A student who has just run ``pip install`` has no engine yet, so the useful
check is the one that needs none. This builds the packaged fixture, compares
it against a digest shipped beside it, exercises the platform-sensitive
behaviour the cross-platform work fixed, and reports which engines are
visible.

What it does not do is generate a model's input files: the converters write
a simulation's files and start the engine in the same loop, so there is no
generation-only path to call yet. Adding one is the next step, and it is
what CI will run.
"""

import hashlib
import sqlite3
import tempfile
from pathlib import Path

from modfilegen import engines, fixtures, paths, text_files

#: Digests of the databases the packaged sources build, so that a student
#: learns the data arrived intact rather than discovering it three hours
#: later through a wrong result.
REFERENCE = fixtures.SOURCES_DIR / "reference.sha256"


def content_digest(database):
    """A digest of what a database holds, not of its bytes.

    SQLite files are not reproducible -- page order, vacuum state and the
    library version all show through -- so the rows are digested instead:
    every table in name order, every row in column order.
    """
    digest = hashlib.sha256()
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " ORDER BY name"
            )
        ]
        for table in tables:
            digest.update(f"\n[{table}]\n".encode("utf-8"))
            columns = [
                row[1]
                for row in connection.execute(f"PRAGMA table_info([{table}])")
            ]
            order = ", ".join(f"[{name}]" for name in columns)
            digest.update((", ".join(columns) + "\n").encode("utf-8"))
            for row in connection.execute(
                f"SELECT * FROM [{table}] ORDER BY {order}" if columns
                else f"SELECT * FROM [{table}]"
            ):
                digest.update((repr(row) + "\n").encode("utf-8"))
    finally:
        connection.close()
    return digest.hexdigest()


def build_the_fixture(directory):
    """The three packaged databases, built into ``directory``."""
    built = {}
    for name, (_, build, sources) in sorted(fixtures.FIXTURES.items()):
        destination = Path(directory) / f"{name}.db"
        build(destination, sources)
        built[name] = destination
    return built


def reference_digests():
    if not REFERENCE.is_file():
        return {}
    digests = {}
    for line in REFERENCE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        digest, _, name = line.partition("  ")
        digests[name.strip()] = digest.strip()
    return digests


def write_reference(directory=None):
    """Recompute the shipped digests. For a maintainer, after a migration."""
    with tempfile.TemporaryDirectory() as scratch:
        built = build_the_fixture(directory or scratch)
        lines = [
            "# Digests of the rows the packaged fixture sources build.",
            "# Regenerate with modfilegen.selftest.write_reference after a",
            "# documented fixture migration.",
        ]
        lines += [
            f"{content_digest(path)}  {name}"
            for name, path in sorted(built.items())
        ]
    REFERENCE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REFERENCE


# --- the platform-sensitive behaviour -------------------------------------


def platform_checks(directory):
    """What differed between Linux and Windows, checked where it runs.

    Each returns a reason when it fails and None when it holds.
    """
    return [
        ("text files are UTF-8 with LF", _check_text_files(directory)),
        ("paths split into components", _check_paths()),
        ("APSIM dates are month names", _check_apsim_dates()),
        ("DSSAT dates survive a year boundary", _check_dssat_dates()),
    ]


def _check_text_files(directory):
    sample = Path(directory) / "encoding.txt"
    with open(sample, "w", **text_files.WRITE) as stream:
        stream.write("degré 20\nligne 2\n")
    raw = sample.read_bytes()
    if b"\r\n" in raw:
        return "a line ending was translated to CRLF"
    if "degré".encode("utf-8") not in raw:
        return "the file was not written as UTF-8"
    return None


def _check_paths():
    import os

    native = os.path.join("tmp", "sim-1", "5.925_6.025", "2000")
    for spelling in (native, "tmp/sim-1/5.925_6.025/2000"):
        if paths.path_parts(spelling)[-3:] != ("sim-1", "5.925_6.025", "2000"):
            return f"{spelling!r} did not split into its components"
    return None


def _check_apsim_dates():
    import datetime

    from modfilegen.Converter.ApsimConverter import apsimmanagementconverter

    months = apsimmanagementconverter.APSIM_MONTHS
    if len(months) != 12 or months[0] != "jan":
        return "the month names are not the twelve APSIM expects"
    if months[datetime.date(2000, 3, 1).month - 1] != "mar":
        return "a month name did not match its number"
    return None


def _check_dssat_dates():
    from modfilegen.Converter.DssatConverter.dssatxconverter import (
        format_dssat_yyddd,
    )

    for year, day, expected in (
        (2001, 150, "01150"),
        (2000, 367, "01001"),
        (2001, -5, "00361"),
    ):
        if format_dssat_yyddd(year, day) != expected:
            return f"{year}/{day} formatted as {format_dssat_yyddd(year, day)}"
    return None


# --- the report -----------------------------------------------------------


def run(stream, directory=None):
    """Check this installation. Returns the process exit status."""
    problems = []

    with tempfile.TemporaryDirectory() as scratch:
        workspace = Path(directory or scratch)
        workspace.mkdir(parents=True, exist_ok=True)

        stream.write("The packaged fixture\n")
        expected = reference_digests()
        try:
            built = build_the_fixture(workspace)
        except Exception as error:
            stream.write(f"  could not be built: {type(error).__name__}: {error}\n")
            return 1
        for name, path in sorted(built.items()):
            digest = content_digest(path)
            if name not in expected:
                stream.write(f"  {name}: built, no reference to compare\n")
            elif digest == expected[name]:
                stream.write(f"  {name}: built and matches\n")
            else:
                stream.write(f"  {name}: built but DIFFERS from the reference\n")
                problems.append(f"{name} does not match its shipped digest")

        stream.write("\nThis platform\n")
        for what, reason in platform_checks(workspace):
            stream.write(f"  {what}: {'ok' if reason is None else reason}\n")
            if reason is not None:
                problems.append(f"{what}: {reason}")

        stream.write("\nModel engines\n")
        for name in sorted(engines.ENGINES):
            finding = engines.inspect(name)
            stream.write(f"  {finding['label']}: {finding['status']}\n")

    stream.write("\n")
    if problems:
        for problem in problems:
            stream.write(f"FAILED: {problem}\n")
        return 1
    # A missing engine is not a failure: generating input files needs none,
    # and a student checks the install before fetching any model.
    stream.write(
        "This installation is sound. Engines reported as missing are not a"
        " failure: see the documentation on obtaining them.\n"
    )
    return 0
