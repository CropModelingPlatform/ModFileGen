"""Locate each model's executable, on Linux, Windows and macOS.

Resolution order, for every engine:

1. its ``GlobalVariables`` key, when the caller set one;
2. its environment variable, for a machine-wide setting that does not need
   editing a notebook;
3. its command name on PATH -- on Windows ``shutil.which`` also tries the
   PATHEXT suffixes, so ``Models`` finds ``Models.exe``;
4. the install locations known for this platform, starting with
   ``~/.modfilegen/engines``, where a portable copy can be unpacked without
   administrator rights;
5. the bare command name, so a failure still names what was looked for.

STICS is deliberately not looked up on PATH: v9 and v11 ship the very same
``stics_modulo`` file name, so PATH cannot tell them apart and picking the
wrong one would silently run the wrong model version.

Always resolve in ``main()``, never inside a worker: a loky worker re-imports
this package and only ever sees the ``GlobalVariables`` defaults.
"""

import os
import shutil
import sys
from pathlib import Path

__all__ = ["ENGINES", "resolve", "not_found", "describe"]

#: Where a portable, no-administrator install unpacks the engines.
PORTABLE_ROOT = Path.home() / ".modfilegen" / "engines"

_WINDOWS = os.name == "nt"
_MACOS = sys.platform == "darwin"


class Engine:
    """How to find one model executable.

    ``commands`` are names to look up on PATH, left empty when the name is
    ambiguous between versions. ``locations`` are paths tried in order; a
    relative one is taken under :data:`PORTABLE_ROOT`. On Windows each is
    also tried with ``.exe`` appended.
    """

    def __init__(self, label, config_key, env_var, commands=(), locations=()):
        self.label = label
        self.config_key = config_key
        self.env_var = env_var
        self.commands = tuple(commands)
        self.locations = tuple(locations)

    def candidates(self):
        for location in self.locations:
            path = Path(location)
            if not path.is_absolute():
                path = PORTABLE_ROOT / path
            yield path
            if _WINDOWS:
                yield path.with_name(path.name + ".exe")

    @property
    def fallback(self):
        """What to return when nothing was found: a name, not a guess."""
        return self.commands[0] if self.commands else str(
            next(iter(self.candidates()), self.config_key)
        )


def _stics(version, container_path):
    return Engine(
        label=f"STICS {version}",
        config_key=f"stics{version.upper()}Executable",
        env_var=f"MODFILEGEN_STICS_{version.upper()}",
        # No PATH lookup on purpose: v9 and v11 share the stics_modulo name.
        commands=(),
        locations=(
            f"stics{version.lower()}/bin/stics_modulo",
            container_path,
        ),
    )


ENGINES = {
    "stics_v9": _stics("v9", "/opt/stics/bin/stics_modulo"),
    "stics_v11": _stics("v11", "/opt/sticsv11/bin/stics_modulo"),
    "dssat_v47": Engine(
        label="DSSAT v4.7",
        config_key="dssatExecutable",
        env_var="MODFILEGEN_DSSAT_V47",
        commands=("dssat",),
        locations=(
            "dssat47/dscsm047",
            "/usr/share/dssat/dscsm047",
            # The directory the official Windows installer defaults to.
            r"C:\DSSAT47\DSCSM047.EXE",
        ),
    ),
    "dssat_v48": Engine(
        label="DSSAT v4.8",
        config_key="dssatV48Executable",
        env_var="MODFILEGEN_DSSAT_V48",
        commands=("dssatv48",),
        locations=(
            "dssat48/dscsm048",
            "/usr/share/dssatv48/dscsm048",
            r"C:\DSSAT48\DSCSM048.EXE",
        ),
    ),
    "apsim": Engine(
        label="APSIM Next Generation",
        config_key="apsim_path",
        env_var="MODFILEGEN_APSIM",
        commands=("Models",),
        locations=(
            "apsim/Models",
            "/usr/share/apsim/Models",
        ),
    ),
    "celsius_v32": Engine(
        label="CELSIUS V32",
        config_key="celsiusV32Executable",
        env_var="MODFILEGEN_CELSIUS_V32",
        commands=("celsiusV32", "CelsiusCli"),
        locations=(
            "celsiusV32/CelsiusCli",
            "/usr/share/celsiusV32/CelsiusCli",
        ),
    ),
    "celsius_v3": Engine(
        label="CELSIUS v3",
        config_key="celsiusExecutable",
        env_var="MODFILEGEN_CELSIUS_V3",
        commands=("celsius",),
        locations=("celsius/celsius", "/usr/share/celsius/celsius"),
    ),
    "datamill": Engine(
        label="DataMill",
        config_key="datamillExecutable",
        env_var="MODFILEGEN_DATAMILL",
        commands=("datamill",),
        locations=("datamill/datamill", "/usr/share/datamill/datamill"),
    ),
}


def _configured(engine):
    from modfilegen import GlobalVariables

    return GlobalVariables.get(engine.config_key) or None


def resolve(name, configured=None):
    """The executable to run for engine ``name``.

    ``configured`` overrides the ``GlobalVariables`` lookup, for callers that
    already hold the value. Never raises: an engine that cannot be found
    comes back as its command name, so the run fails where it is reported
    with the model's own error handling.
    """
    engine = ENGINES[name]

    explicit = configured or _configured(engine) or os.environ.get(engine.env_var)
    if explicit:
        explicit = str(explicit)
        # A full path is taken as given. A bare name goes through PATH, so
        # "Models" becomes Models.exe on Windows; if that fails the name is
        # returned unchanged, and the failure names what was looked for.
        if Path(explicit).is_file():
            return explicit
        return shutil.which(explicit) or explicit

    for command in engine.commands:
        found = shutil.which(command)
        if found:
            return found

    for candidate in engine.candidates():
        if candidate.is_file():
            return str(candidate)

    return engine.fallback


def describe(name):
    """How to tell ModFileGen where this engine is. For error messages."""
    engine = ENGINES[name]
    lines = [
        f"Set GlobalVariables[{engine.config_key!r}] to its full path,",
        f"or export {engine.env_var}=/path/to/the/executable.",
    ]
    if engine.commands:
        lines.append(
            "It is also found automatically when "
            + " or ".join(engine.commands)
            + " is on PATH."
        )
    lines.append(
        f"A portable copy is picked up under {PORTABLE_ROOT / '<engine>'}, "
        "which needs no administrator rights."
    )
    return " ".join(lines)


def not_found(name, executable):
    """The error to raise when the resolved executable will not run."""
    engine = ENGINES[name]
    return FileNotFoundError(
        f"{engine.label} could not be run as {executable!r}. {describe(name)}"
    )
