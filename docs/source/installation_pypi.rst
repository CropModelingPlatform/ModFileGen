Installing and checking the package
===================================

.. code-block:: bash

    pip install modfilegen
    agriscale selftest

``selftest`` needs no model engine, which is the point: a student who has
just installed has none yet. It builds the demo databases that ship with the
package, compares them against a digest shipped beside them, checks the
behaviour that differs between operating systems, and lists which engines
are visible.

What it checks
--------------

**The packaged fixture.** Three databases are built from the CSV sources in
the wheel and their rows digested. A mismatch means the data did not arrive
intact, which is better learnt now than three hours later through a wrong
result. The digest covers the rows, not the file: SQLite files are not
reproducible, as page order and library version show through.

**This platform.** One check per defect the cross-platform work fixed:
text files written as UTF-8 with LF whatever the locale, paths split into
components whatever the separator, APSIM dates written as month names rather
than through a glibc-only ``strftime``, and DSSAT dates surviving a year
boundary in both directions.

**The engines.** Reported, not required. A missing engine is not a failure:
generating input files needs none. See :doc:`engines`.

The exit status is 0 when the installation is sound and 1 otherwise, so it
can be used in a script or a continuous-integration job.

Running the demo
----------------

The package carries a small rotation -- one point, one soil, 2000 to 2002, a
maize-peanut-maize succession and a two-crop association -- with the plant
and genotype files it refers to:

.. code-block:: bash

    agriscale fixture --out data

That writes the databases and prints the command to run next, with the right
paths filled in. Nothing else is needed: no repository checkout, no
developer database.

A simulation then needs an engine, which :doc:`engines` explains how to
obtain, and :doc:`command_line` how to point at.

What the self-test does not do
------------------------------

It does not generate a model's input files. The converters write a
simulation's files and start the engine in the same loop, so there is no
generation-only path to call yet. Until there is, the self-test proves the
installation is sound and the demo data intact, and the first real run
proves the rest.
