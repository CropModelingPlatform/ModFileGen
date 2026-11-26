"""Launch STICS v11 on one USM and collect its reports.

Replaces ``sticsrun.sh``. The outputs keep the names the readers expect:
``collect_reports`` opens ``mod_rapport{,A,P}_<key>.sti`` and
``create_df_daily`` globs ``mod_s_<key>__mod_s*.sti`` and
``mod_profil_<key>__mod_profil*.sti``, so the ``__<stem>`` part is part of
the contract, not decoration.

The ``sed -i -z`` that patched ``codeseprapport`` is gone: ``common_tempopar``
now generates 2 directly.
"""

import os

from modfilegen import GlobalVariables, engine_runner

#: Where the AgriscaleContainer image installs STICS v11.
DEFAULT_EXECUTABLE = "/opt/sticsv11/bin/stics_modulo"

TIMEOUT = 180

#: Reports of a single-crop USM, and of the principal/associated crops.
REPORTS = ("mod_rapport.sti", "mod_rapportA.sti", "mod_rapportP.sti")


def resolve_executable():
    """The configured STICS v11 executable, else the container default.

    Call this from ``main()``, never from a worker: ``GlobalVariables`` does
    not cross the process boundary.
    """
    return GlobalVariables.get("sticsV11Executable") or DEFAULT_EXECUTABLE


def run_stics(usmdir, output_dir, dt, dailyoutput, executable=None, timeout=TIMEOUT):
    """Run STICS v11 in ``usmdir`` and copy its outputs to ``output_dir``.

    Returns the ``CompletedProcess``. Raises ``CalledProcessError`` on a
    non-zero exit and ``TimeoutExpired`` past ``timeout``, as the shell
    launch did.
    """
    executable = executable or resolve_executable()
    result = engine_runner.run_engine(
        executable, cwd=usmdir, timeout=timeout
    )

    base = os.path.basename(os.path.normpath(usmdir))
    for report in REPORTS:
        stem = report[: -len(".sti")]
        engine_runner.copy_output(usmdir, report, output_dir, f"{stem}_{base}.sti")

    if int(dailyoutput) == 1:
        engine_runner.copy_outputs(
            usmdir,
            "mod_s*.sti",
            output_dir,
            rename=lambda path: f"mod_s_{base}__{path.stem}.sti",
        )
        engine_runner.copy_outputs(
            usmdir,
            "mod_profil*.sti",
            output_dir,
            rename=lambda path: f"mod_profil_{base}__{path.stem}.sti",
        )

    if int(dt) == 1:
        engine_runner.remove_usm(usmdir)

    return result
