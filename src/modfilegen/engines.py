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

__all__ = [
    "ENGINES",
    "resolve",
    "not_found",
    "describe",
    "guidance",
    "set_variable",
]

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

    def __init__(
        self, label, config_key, env_var, commands=(), locations=(),
        companions=(),
    ):
        self.label = label
        self.config_key = config_key
        self.env_var = env_var
        self.commands = tuple(commands)
        self.locations = tuple(locations)
        #: Glob patterns an engine needs beside its executable. Copying the
        #: binary alone is a common mistake: DSSAT reads DSSATPRO for its
        #: data directories, and APSIM needs its 61 assemblies.
        self.companions = tuple(companions)

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
        companions=("DSSATPRO.*",),
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
        companions=("DSSATPRO.*",),
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
        companions=("*.dll",),
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
        companions=("*.dll",),
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


def _resolve(name, configured=None):
    """The executable for ``name``, and which link of the cascade found it."""
    engine = ENGINES[name]

    for value, origin in (
        (configured, "given"),
        (_configured(engine), f"GlobalVariables[{engine.config_key!r}]"),
        (os.environ.get(engine.env_var), engine.env_var),
    ):
        if not value:
            continue
        value = str(value)
        # A full path is taken as given. A bare name goes through PATH, so
        # "Models" becomes Models.exe on Windows; if that fails the name is
        # returned unchanged, and the failure names what was looked for.
        if Path(value).is_file():
            return value, origin
        return shutil.which(value) or value, origin

    for command in engine.commands:
        found = shutil.which(command)
        if found:
            return found, "PATH"

    for candidate in engine.candidates():
        if candidate.is_file():
            return str(candidate), "install location"

    return engine.fallback, "not found"


def resolve(name, configured=None):
    """The executable to run for engine ``name``.

    ``configured`` overrides the ``GlobalVariables`` lookup, for callers that
    already hold the value. Never raises: an engine that cannot be found
    comes back as its command name, so the run fails where it is reported
    with the model's own error handling.
    """
    return _resolve(name, configured)[0]


def inspect(name, configured=None):
    """What is known about engine ``name`` on this machine.

    Reports where it was found and whether it could actually run, so a
    student can tell "ModFileGen cannot see my install" from "the install
    itself is incomplete" without reading any code. Nothing is executed:
    starting a crop model to ask whether it exists would do real work.
    """
    engine = ENGINES[name]
    executable, origin = _resolve(name, configured)
    path = Path(executable)

    exists = path.is_file()
    missing = []
    if exists:
        # The companions sit next to the real file, not next to the symlink
        # that points at it: /usr/bin/dssat is a link into /usr/share/dssat,
        # where DSSATPRO actually lives.
        home = path.resolve().parent
        for pattern in engine.companions:
            if not any(home.glob(pattern)):
                missing.append(pattern)

    if not exists:
        status = "missing"
    elif missing:
        status = "incomplete"
    elif os.name != "nt" and not os.access(path, os.X_OK):
        status = "not executable"
    else:
        status = "ok"

    return {
        "engine": name,
        "label": engine.label,
        "executable": executable,
        "origin": origin,
        "status": status,
        "missing_companions": missing,
    }


def _startup_file():
    """The file a POSIX shell reads on login, so the setting lasts.

    This is the counterpart of Windows' setx: without it the advice sets a
    variable that dies with the terminal, and the engine goes missing again
    tomorrow with nothing to show why.
    """
    shell = os.environ.get("SHELL", "")
    if shell.endswith("zsh"):
        return "~/.zshrc"
    if shell.endswith(("csh", "tcsh")):
        return "~/.cshrc"
    return "~/.bashrc"


def _in_a_posix_shell():
    """Whether the shell around us takes ``export``, even on Windows.

    Git Bash, MSYS and a WSL prompt all run on Windows yet speak sh. Judging
    by ``os.name`` alone would hand those users cmd syntax they cannot run.
    """
    if not _WINDOWS:
        return True
    if os.environ.get("MSYSTEM") or os.environ.get("WSL_DISTRO_NAME"):
        return True
    return os.environ.get("SHELL", "").replace("\\", "/").rsplit("/", 1)[-1] in (
        "bash", "zsh", "sh", "dash", "bash.exe", "sh.exe"
    )


def _posix_lines(env_var, path):
    return [
        f"bash/zsh:   export {env_var}={path}   (this shell only)",
        f"            echo 'export {env_var}={path}' >> {_startup_file()}"
        "   (lasting)",
    ]


def _windows_lines(env_var, path):
    # Quoting the whole assignment keeps a stray trailing space out of the
    # value, which is cmd.exe's classic way of silently doing nothing. setx
    # writes to the user's own profile, so it needs no administrator rights,
    # but it only reaches windows opened afterwards.
    return [
        f'cmd:        set "{env_var}={path}"   (this window only)',
        f'            setx {env_var} "{path}"  (lasting, new windows)',
        f'PowerShell: $env:{env_var} = "{path}"',
    ]


def set_variable(env_var):
    """Shell lines that set ``env_var``, the likeliest shell first.

    "export VAR=/path/to/it" is wrong twice over on cmd.exe: there is no
    export, and the path spelling is not its own. A student followed that
    advice literally -- ``set export VAR=...``, which defines a variable
    named "export VAR" -- and got the same advice back unchanged. Advice
    that cannot work is worse than none.

    Every spelling is listed, because the shell cannot be known for certain:
    Git Bash and WSL run sh on Windows, and a detection that guessed wrong
    and showed nothing else would strand the reader. Ordering is the guess;
    completeness is the guarantee.
    """
    posix = _posix_lines(env_var, "/path/to/the/executable")
    windows = _windows_lines(env_var, r"C:\path\to\the\executable.exe")
    if _in_a_posix_shell():
        return posix + ([] if not _WINDOWS else windows)
    return windows + posix


def guidance(name):
    """How to tell ModFileGen where engine ``name`` is, as separate lines."""
    engine = ENGINES[name]
    lines = [f"Set GlobalVariables[{engine.config_key!r}] to its full path, or:"]
    lines += set_variable(engine.env_var)
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
    return lines


def describe(name):
    """The same guidance as one string, for a single-line error message."""
    return " ".join(line.strip() for line in guidance(name))


def not_found(name, executable):
    """The error to raise when the resolved executable will not run."""
    engine = ENGINES[name]
    return FileNotFoundError(
        f"{engine.label} could not be run as {executable!r}. {describe(name)}"
    )
