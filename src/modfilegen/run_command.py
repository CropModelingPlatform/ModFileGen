"""Driving one model run from the command line.

A notebook was the only way to start a model: it needs its paths edited by
hand in a cell, it reports success by printing, and it returns no exit
status, so nothing -- not a student, not CI -- can check whether the run
worked. This turns the same sequence into one command.

The command only fills ``GlobalVariables`` and calls the dispatcher the
notebooks call. Nothing is reimplemented here and nothing runs per
simulation, so the parallel path and its performance are untouched.
"""

import hashlib
import os
import re
from pathlib import Path, PurePath

from modfilegen import GlobalVariables, engines


class Model:
    """How one model is selected and configured from the command line."""

    def __init__(
        self, label, dispatch, engine_by_version, default_version=None,
        version_key=None, mode_key=None, modes=("standard",),
        needs_cultivars=False, needs_celsius_db=False, needs_package=False,
    ):
        self.label = label
        #: Name of the dispatcher in modfilegen.Converter, called as-is.
        self.dispatch = dispatch
        #: Version accepted on the command line -> name in modfilegen.engines.
        self.engine_by_version = dict(engine_by_version)
        self.default_version = default_version
        self.version_key = version_key
        self.mode_key = mode_key
        self.modes = tuple(modes)
        self.needs_cultivars = needs_cultivars
        self.needs_celsius_db = needs_celsius_db
        self.needs_package = needs_package

    @property
    def versions(self):
        return tuple(self.engine_by_version)


MODELS = {
    "stics": Model(
        label="STICS",
        dispatch="run_stics",
        engine_by_version={"v9": "stics_v9", "v11": "stics_v11"},
        default_version="v11",
        version_key="stics_version",
        mode_key="stics_mode",
        modes=("standard", "successive"),
        needs_cultivars=True,
        # STICS reads <package>/data/stics_params when it exists, and v11
        # successive refuses to start without the key set at all.
        needs_package=True,
    ),
    "dssat": Model(
        label="DSSAT",
        dispatch="run_dssat",
        engine_by_version={"v47": "dssat_v47", "v48": "dssat_v48"},
        default_version="v47",
        version_key="dssat_version",
        mode_key="dssat_mode",
        modes=("standard", "successive"),
        needs_cultivars=True,
    ),
    "apsim": Model(
        label="APSIM Next Generation",
        dispatch="run_apsim",
        engine_by_version={"ng": "apsim"},
        default_version="ng",
    ),
    "celsius": Model(
        label="CELSIUS",
        dispatch="run_celsius",
        engine_by_version={"v3": "celsius_v3", "v32": "celsius_v32"},
        default_version="v3",
        version_key="celsius_version",
        mode_key="celsius_mode",
        modes=("standard", "successive"),
        needs_celsius_db=True,
    ),
}


class Problem(Exception):
    """A misconfiguration to report as a message, not a traceback."""


def _existing(path, what):
    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise Problem(f"{what} does not exist: {resolved}")
    return resolved


def settings(arguments):
    """The ``GlobalVariables`` this run needs, as a plain dict.

    Returned rather than applied, so a caller can see the whole decision --
    and so a test can check it without running a model.
    """
    model = MODELS[arguments.model]

    version = arguments.version or model.default_version
    if version not in model.engine_by_version:
        raise Problem(
            f"{model.label} has no version {version!r}; expected "
            + " or ".join(repr(known) for known in model.versions)
        )
    if arguments.mode not in model.modes:
        raise Problem(
            f"{model.label} has no {arguments.mode!r} mode; expected "
            + " or ".join(repr(known) for known in model.modes)
        )

    output = Path(arguments.out).expanduser()
    temporary = Path(arguments.temp).expanduser() if arguments.temp else output / "temp"

    values = {
        "dbMasterInput": str(_existing(arguments.master_input, "the MasterInput database")),
        "dbModelsDictionary": str(
            _existing(arguments.models_dictionary, "the ModelsDictionary database")
        ),
        "directorypath": str(output),
        "tempDir": str(temporary),
        "nthreads": arguments.threads,
        "parts": arguments.parts,
        # Keeping the intermediate USM directories is the default here, and
        # the opposite of the library default: on a first run they are the
        # only evidence of what the engine was given. --delete-intermediate
        # asks for the library behaviour.
        "dt": 1 if arguments.delete_intermediate else 0,
        "dailyoutput": 1 if arguments.daily_output else 0,
    }

    if model.version_key:
        values[model.version_key] = version
    if model.mode_key:
        values[model.mode_key] = arguments.mode
    if model.needs_package:
        # The directory holding this installed package, not a path the
        # caller has to know: it only carries optional STICS overrides.
        values["package"] = str(Path(__file__).resolve().parent)
    if model.needs_cultivars:
        if not arguments.cultivars:
            raise Problem(
                f"{model.label} needs --cultivars: the folder holding its "
                "plant and genotype files"
            )
        values["pltfolder"] = str(_existing(arguments.cultivars, "the cultivars folder"))
    if model.needs_celsius_db:
        if not arguments.celsius_db:
            raise Problem(f"{model.label} needs --celsius-db")
        values["dbCelsius"] = str(_existing(arguments.celsius_db, "the CELSIUS database"))

    if arguments.executable:
        engine = model.engine_by_version[version]
        values[engines.ENGINES[engine].config_key] = str(
            _existing(arguments.executable, "the engine executable")
        )

    return values


def _digest(path):
    """SHA-256 of one file, read in blocks so a large output is not loaded."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


#: Every model names its summary CSV "<uuid4>_<model>.csv", so that parallel
#: runs and successive runs into one directory cannot collide. The identifier
#: belongs to the run, not to the content.
_RUN_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_", re.I
)


def comparable_name(name):
    """``name`` with a leading run identifier replaced by a fixed token.

    Without this the manifest could not do the one job it has. Two runs of
    the same inputs produce the same bytes under different names, so a diff
    of the two manifests would report every file as changed and nothing as
    equal -- the opposite of the truth.
    """
    head, _, tail = name.rpartition("/")
    replaced = _RUN_ID.sub("<run-id>_", tail)
    return f"{head}/{replaced}" if head else replaced


def manifest(output, skip=()):
    """``(relative path, sha256)`` for every file under ``output``.

    Paths use forward slashes, a leading run identifier is replaced, and the
    rows are sorted, so a manifest made on Windows can be compared with one
    made on Linux byte for byte. That comparison is the point: it is how a
    run on a student's machine is checked against a known-good one.
    """
    output = Path(output)
    skipped = {Path(path).resolve() for path in skip}
    rows = []
    for path in sorted(output.rglob("*")):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if any(
            resolved == ignored or ignored in resolved.parents for ignored in skipped
        ):
            continue
        name = "/".join(PurePath(path.relative_to(output)).parts)
        rows.append((comparable_name(name), _digest(path)))
    return sorted(rows)


def write_manifest(destination, rows, stream=None):
    from modfilegen import text_files

    with open(destination, "w", **text_files.WRITE) as handle:
        for name, digest in rows:
            handle.write(f"{digest}  {name}\n")
    if stream is not None:
        stream.write(f"{len(rows)} files listed in {destination}\n")


def perform(arguments, stream):
    """Configure and start one run. Returns the process exit status."""
    from importlib import import_module

    try:
        values = settings(arguments)
    except Problem as problem:
        stream.write(f"{problem}\n")
        return 2

    model = MODELS[arguments.model]
    engine = model.engine_by_version[arguments.version or model.default_version]
    finding = engines.inspect(engine, values.get(engines.ENGINES[engine].config_key))
    stream.write(f"{finding['label']}: {finding['status']}")
    stream.write(
        f" ({finding['executable']})\n" if finding["status"] != "missing" else "\n"
    )
    if finding["status"] != "ok":
        # Said before the run, not after: generating the inputs takes real
        # time, and failing at the end over a path is a poor trade.
        for line in engines.guidance(engine):
            stream.write(f"  {line}\n")
        return 1

    output = Path(values["directorypath"])
    output.mkdir(parents=True, exist_ok=True)
    Path(values["tempDir"]).mkdir(parents=True, exist_ok=True)

    GlobalVariables.update(values)
    stream.write(f"Writing to {output}\n")

    dispatch = getattr(import_module("modfilegen.Converter"), model.dispatch)
    try:
        dispatch()
    except Exception as error:  # the converters raise plain exceptions
        stream.write(f"The run failed: {type(error).__name__}: {error}\n")
        # An engine's own exit status says nothing about why. What does is
        # the USM directory it was given, which is still on disk unless
        # --delete-intermediate asked otherwise.
        scratch = Path(values["tempDir"])
        if not arguments.delete_intermediate and any(scratch.glob("*")):
            stream.write(f"The files the engine was given are kept in {scratch}\n")
        return 1

    if arguments.manifest:
        write_manifest(
            arguments.manifest, manifest(output, skip=[values["tempDir"]]), stream
        )
    return 0


def add_arguments(parser):
    """The ``run`` options. Kept here so the parser stays readable."""
    parser.add_argument(
        "--model", required=True, choices=sorted(MODELS),
        help="which model to run",
    )
    parser.add_argument(
        "--version",
        help="model version: "
        + "; ".join(
            f"{name} {'/'.join(model.versions)}" for name, model in sorted(MODELS.items())
        ),
    )
    parser.add_argument(
        "--mode", default="standard", choices=("standard", "successive"),
        help="successive runs chain seasons; not every model supports it",
    )
    parser.add_argument("--master-input", required=True, help="MasterInput database")
    parser.add_argument(
        "--models-dictionary", required=True, help="ModelsDictionary database"
    )
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument(
        "--cultivars", help="folder of plant and genotype files (STICS, DSSAT)"
    )
    parser.add_argument("--celsius-db", help="CELSIUS database (CELSIUS only)")
    parser.add_argument(
        "--executable",
        help="the engine to run, overriding the environment and the search",
    )
    parser.add_argument("--threads", type=int, default=1, help="worker processes")
    parser.add_argument("--parts", type=int, default=1, help="data partitions")
    parser.add_argument("--temp", help="scratch directory (default: <out>/temp)")
    parser.add_argument(
        "--daily-output", action="store_true", help="also produce daily output"
    )
    parser.add_argument(
        "--delete-intermediate", action="store_true",
        help="delete each USM directory after it has run (dt=1)",
    )
    parser.add_argument(
        "--manifest", help="write a sha256 listing of the output, for comparing runs"
    )
    return parser
