"""Launch DSSAT on one USM and collect its outputs.

Replaces ``dssatrun.sh`` (batch mode ``B``) and ``dssatrun_successive.sh``
(sequence mode ``Q``). The version picks both the executable and the batch
file name, as the scripts did: v4.7 uses ``DSSBatch.v47``, v4.8
``DSSBatch.v48``.

``stderr`` is deliberately left to the caller: DSSAT standard scans it for
``STOP 99``, and the successive converter reads ``ERROR.OUT`` afterwards.
"""

import os
import subprocess
import sys

from modfilegen import GlobalVariables, engine_runner

#: Executable and batch file per DSSAT version. The names are the symlinks
#: the AgriscaleContainer image puts on PATH.
VERSIONS = {
    "v47": {"executable": "dssat", "batch": "DSSBatch.v47", "key": "dssatExecutable"},
    "v48": {"executable": "dssatv48", "batch": "DSSBatch.v48", "key": "dssatV48Executable"},
}

BATCH_TIMEOUT = 300
SEQUENCE_TIMEOUT = 600

#: Daily outputs the batch run copies when dailyoutput is on.
DAILY_OUTPUTS = (
    "ET.OUT",
    "PlantGro.OUT",
    "PlantN.OUT",
    "SoilOrg.OUT",
    "SoilWat.OUT",
    "Weather.OUT",
)


def _version(dssat_version):
    try:
        return VERSIONS[dssat_version]
    except KeyError:
        raise ValueError(
            f"Unsupported DSSAT version {dssat_version!r}; expected v47 or v48"
        ) from None


def resolve_executable(dssat_version="v47"):
    """The configured DSSAT executable for this version, else its PATH name.

    Call this from ``main()``, never from a worker: ``GlobalVariables`` does
    not cross the process boundary.
    """
    version = _version(dssat_version)
    return GlobalVariables.get(version["key"]) or version["executable"]


def batch_file(dssat_version="v47"):
    """The DSSBatch file name the X-file writer and the run must agree on."""
    return _version(dssat_version)["batch"]


def run_batch(
    usmdir,
    output_dir,
    dt,
    dailyoutput=0,
    dssat_version="v47",
    summary_id=None,
    executable=None,
    timeout=BATCH_TIMEOUT,
    check=False,
    stderr=subprocess.PIPE,
):
    """Run DSSAT in batch mode (``B``) and collect Summary.OUT.

    ``summary_id`` names the copied summary; it defaults to the USM directory
    name, which is what ``basename "$USM_DIR"`` gave the scripts.

    ``check=False`` is the default because DSSAT standard inspects the return
    code and stderr itself to tell a ``STOP 99`` from an ordinary failure.
    The caller decides, so nothing is swallowed here.
    """
    version = _version(dssat_version)
    executable = executable or resolve_executable(dssat_version)

    result = engine_runner.run_engine(
        executable,
        ["B", version["batch"]],
        cwd=usmdir,
        timeout=timeout,
        check=check,
        stderr=stderr,
    )

    base = os.path.basename(os.path.normpath(usmdir))
    identifier = base if summary_id is None else summary_id
    engine_runner.copy_output(
        usmdir, "Summary.OUT", output_dir, f"Summary_{identifier}.OUT"
    )

    if int(dailyoutput) == 1:
        for name in DAILY_OUTPUTS:
            stem = name[: -len(".OUT")]
            engine_runner.copy_output(
                usmdir, name, output_dir, f"{stem}_{base}.out"
            )

    if int(dt) == 1:
        engine_runner.remove_usm(usmdir)

    return result


def run_sequence(
    usmdir,
    output_dir,
    summary_id,
    dssat_version="v47",
    executable=None,
    timeout=SEQUENCE_TIMEOUT,
    check=True,
    stderr=None,
):
    """Run DSSAT in sequence mode (``Q``) and collect Summary.OUT.

    Successive simulations chain inside one run, so the USM directory is kept
    and no daily output is copied, exactly as ``dssatrun_successive.sh`` did.
    """
    version = _version(dssat_version)
    executable = executable or resolve_executable(dssat_version)

    result = engine_runner.run_engine(
        executable,
        ["Q", version["batch"]],
        cwd=usmdir,
        timeout=timeout,
        check=check,
        stderr=sys.stderr if stderr is None else stderr,
    )

    engine_runner.copy_output(
        usmdir, "Summary.OUT", output_dir, f"Summary_{summary_id}.OUT"
    )
    return result
