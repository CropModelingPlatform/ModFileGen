"""Launch STICS v9 on one USM and collect its reports.

Replaces ``sticsrun.sh``. v9 differs from v11 on purpose, and the differences
are contracts the readers depend on:

* v9 has no associated crops, so there is one report, ``mod_rapport.sti``,
  and no ``mod_rapportA``/``mod_rapportP``;
* the daily output is a single file named ``mod_s_<base>.sti`` without the
  source stem, and the profile is the exact name ``mod_profil.sti``, not a
  glob. ``main()`` opens both paths directly.

The ``sed -i -z`` that patched ``codeseprapport`` is gone: ``common_tempopar``
now generates 2 directly.
"""

import os

from modfilegen import engine_runner, engines

ENGINE = "stics_v9"

TIMEOUT = 180


def resolve_executable():
    """Where STICS v9 is, see :mod:`modfilegen.engines` for the order.

    Call this from ``main()``, never from a worker: ``GlobalVariables`` does
    not cross the process boundary.
    """
    return engines.resolve(ENGINE)


def run_stics(usmdir, output_dir, dt, dailyoutput, executable=None, timeout=TIMEOUT):
    """Run STICS v9 in ``usmdir`` and copy its outputs to ``output_dir``.

    Returns the ``CompletedProcess``. Raises ``CalledProcessError`` on a
    non-zero exit and ``TimeoutExpired`` past ``timeout``, as the shell
    launch did.
    """
    executable = executable or resolve_executable()
    try:
        result = engine_runner.run_engine(
            executable, cwd=usmdir, timeout=timeout
        )
    except FileNotFoundError as error:
        raise engines.not_found(ENGINE, executable) from error

    base = os.path.basename(os.path.normpath(usmdir))
    engine_runner.copy_output(
        usmdir, "mod_rapport.sti", output_dir, f"mod_rapport_{base}.sti"
    )

    if int(dailyoutput) == 1:
        engine_runner.copy_outputs(
            usmdir,
            "mod_s*.sti",
            output_dir,
            rename=lambda path: f"mod_s_{base}.sti",
            first_only=True,
        )
        engine_runner.copy_output(
            usmdir, "mod_profil.sti", output_dir, f"mod_profil_{base}.sti"
        )

    if int(dt) == 1:
        engine_runner.remove_usm(usmdir)

    return result
