Running a model from the command line
=====================================

``agriscale run`` generates a model's input files and starts it, with an
exit status: ``0`` when the run finished, ``1`` when it failed, ``2`` when
the options were wrong. A notebook reports success by printing, so nothing
-- no student, no continuous integration -- could check the result; this is
the same sequence with an answer something can act on.

The command only fills ``GlobalVariables`` and calls the dispatcher the
notebooks call. Nothing runs per simulation, so the parallel path and its
speed are untouched.

A first run
-----------

.. code-block:: bat

    agriscale engines
    agriscale run --model stics --version v11 ^
        --master-input data\MasterInput.db ^
        --models-dictionary data\ModelsDictionaryArise.db ^
        --cultivars data\cultivars\stics ^
        --out runs\first --manifest runs\first.sha256

.. code-block:: bash

    agriscale run --model stics --version v11 \
        --master-input data/MasterInput.db \
        --models-dictionary data/ModelsDictionaryArise.db \
        --cultivars data/cultivars/stics \
        --out runs/first --manifest runs/first.sha256

Check the engine first. ``agriscale run`` resolves it and stops before
generating anything when it is not usable: building the inputs takes real
time, and failing at the end over a path that was wrong from the start is a
poor trade.

Choosing the model
------------------

===========  ================  ============================  =================
``--model``  ``--version``     ``--mode``                    Also needs
===========  ================  ============================  =================
``stics``    ``v9``, ``v11``   ``standard``, ``successive``  ``--cultivars``
``dssat``    ``v47``, ``v48``  ``standard``, ``successive``  ``--cultivars``
``apsim``    (none)            ``standard``                  (none)
``celsius``  ``v3``, ``v32``   ``standard``, ``successive``  ``--celsius-db``
===========  ================  ============================  =================

``--version`` defaults to the version each model's configuration already
defaults to. ``successive`` chains the seasons of a rotation; it exists for
STICS v11, DSSAT and CELSIUS V32 only, and asking for it elsewhere is
refused by name rather than deep inside a converter.

Pointing at the engine
----------------------

``--executable`` overrides everything else for this run, which is the
quickest way to try a build without changing a setting:

.. code-block:: bash

    agriscale run --model stics --version v11 \
        --executable ~/JavaSTICS-v11.0.0/bin/stics_modulo ...

Without it, the usual search applies -- the ``GlobalVariables`` key, then
the environment variable, then the known locations. See
:doc:`engines`.

Reading a failure
-----------------

Intermediate files are **kept** by default, the opposite of the library's
own default. On a first run they are the only evidence of what the engine
was actually given, and an engine's exit status says nothing about why it
refused. When a run fails, the command names the directory they are in::

    The run failed: CalledProcessError: Command '[...stics_modulo]'
    returned non-zero exit status 9.
    The files the engine was given are kept in runs/first/temp

What to read there is the engine's own log beside the inputs --
``modhistory.sti`` and ``stics_errors.log`` for STICS, which say things a
process exit code cannot, such as::

    ERROR: Error during annual loop: reference height weather measurements
    (zr parameter in station file) has to be higher than the maximum height
    of the crop (hautmax in plant file)

Pass ``--delete-intermediate`` for the library behaviour, which removes each
USM directory once it has run. That is what a long production run wants, and
what a first run should not have.

Parallelism and output volume
-----------------------------

``--threads`` sets the number of worker processes and ``--parts`` the number
of data partitions; both default to 1, which is what a first run wants --
one worker, one partition, and a failure that belongs to a simulation you
can name. Raise them once a run succeeds.

.. warning::

   A worker is a separate process that re-imports the package, so it sees
   the ``GlobalVariables`` defaults and never what a notebook set. The
   engine path is therefore resolved before the workers start, which is why
   ``--executable`` works with ``--threads`` above 1.

``--daily-output`` adds the daily series to the summary output. It is off by
default because it is the bulk of what a run writes.

``--temp`` places the scratch directory somewhere other than ``<out>/temp``.
Two reasons to use it: a disk with room for the intermediate USM
directories, and, on Windows, a short path -- a deep output directory plus
a long USM name reaches the 260-character limit, and the engine then fails
on a path it was handed rather than on its inputs.

Comparing two runs
------------------

``--manifest`` writes a SHA-256 listing of everything under ``--out``, in
the format ``sha256sum`` reads, with forward slashes and sorted. The point
is that a manifest produced on Windows can be compared with one produced on
Linux, byte for byte::

    agriscale run ... --manifest linux.sha256     # on one machine
    agriscale run ... --manifest windows.sha256   # on the other
    diff linux.sha256 windows.sha256

The scratch directory is left out of the listing: the engines write run
timestamps into their raw output, so those files differ between two runs of
the same inputs on the same machine and would drown the comparison.

Every model names its summary CSV ``<uuid4>_<model>.csv``, so that parallel
and repeated runs into one directory cannot collide. That identifier belongs
to the run, not to its content, so the manifest replaces it with
``<run-id>``::

    edc6ce001b029191...47347c21  <run-id>_stics_successive.csv

Without that substitution the manifest could not do the one job it has: two
runs producing the very same bytes would share no single line, and a diff
would report every file as changed.

No manifest is written for a failed run. A partial listing that looks like a
result is worse than none.
