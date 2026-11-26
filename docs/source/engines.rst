Obtaining the model engines
===========================

ModFileGen writes input files on its own; it needs no engine for that. An
engine is needed only to *run* a simulation. The two halves are separate on
purpose, so a student can generate and inspect files on a machine where no
model is installed.

Start by asking what is already found::

    agriscale engines

The report names, for each engine, where it was found and what is missing.
It distinguishes two failures that need different answers:

``not found``
    ModFileGen cannot see the engine. Install it, or tell ModFileGen where
    it is.

``incomplete``
    The engine is there but amputated: the executable was copied away from
    the files it needs beside it. See `What has to sit beside the
    executable`_.

Telling ModFileGen where an engine is
-------------------------------------

Three ways, tried in this order; the first that answers wins.

1. the ``GlobalVariables`` key, set from a notebook or a script;
2. the environment variable, for a machine-wide setting that survives
   outside any notebook;
3. the engine's own command name on ``PATH``, or one of the known install
   locations.

================  ==========================  =========================
Engine            ``GlobalVariables`` key     Environment variable
================  ==========================  =========================
STICS v9          ``sticsV9Executable``       ``MODFILEGEN_STICS_V9``
STICS v11         ``sticsV11Executable``      ``MODFILEGEN_STICS_V11``
DSSAT v4.7        ``dssatExecutable``         ``MODFILEGEN_DSSAT_V47``
DSSAT v4.8        ``dssatV48Executable``      ``MODFILEGEN_DSSAT_V48``
APSIM NG          ``apsim_path``              ``MODFILEGEN_APSIM``
CELSIUS v3        ``celsiusExecutable``       ``MODFILEGEN_CELSIUS_V3``
CELSIUS V32       ``celsiusV32Executable``    ``MODFILEGEN_CELSIUS_V32``
DataMill          ``datamillExecutable``      ``MODFILEGEN_DATAMILL``
================  ==========================  =========================

``agriscale engines`` prints the exact line to run for your own shell, in
its own syntax. For the record:

.. code-block:: bat

    rem Windows, cmd.exe -- this window only
    set "MODFILEGEN_STICS_V11=D:\JavaSTICS-v11.0.0\bin\stics_modulo.exe"
    rem lasting, applies to windows opened afterwards; no admin rights
    setx MODFILEGEN_STICS_V11 "D:\JavaSTICS-v11.0.0\bin\stics_modulo.exe"

.. code-block:: bash

    # Linux, macOS, Git Bash, WSL
    export MODFILEGEN_STICS_V11=~/JavaSTICS-v11.0.0/bin/stics_modulo

.. warning::

   STICS is never taken from ``PATH``. v9 and v11 ship the very same
   ``stics_modulo`` file name, so ``PATH`` cannot tell them apart and the
   wrong version would run silently, with no error and wrong results. The
   two versions are distinguished by their *directory* only, so STICS
   always needs its key, its variable, or one of the known locations.

Without administrator rights
----------------------------

An engine unpacked under ``~/.modfilegen/engines/<engine>`` is picked up
with nothing to configure. That directory is the first place looked at, it
lives in the user's own home, and writing to it needs no administrator
rights, which is the whole point: a student who cannot run an installer can
still unpack a zip.

====================  ==============================================
Engine                Expected path under ``~/.modfilegen/engines``
====================  ==============================================
STICS v9              ``sticsv9/bin/stics_modulo``
STICS v11             ``sticsv11/bin/stics_modulo``
DSSAT v4.7            ``dssat47/dscsm047``
DSSAT v4.8            ``dssat48/dscsm048``
APSIM NG              ``apsim/Models``
CELSIUS v3            ``celsius/celsius``
CELSIUS V32           ``celsiusV32/CelsiusCli``
DataMill              ``datamill/datamill``
====================  ==============================================

On Windows each of these is also tried with ``.exe`` appended, so
``sticsv11\bin\stics_modulo.exe`` is found by the same entry.

Where each engine comes from
----------------------------

Every one of the three public models is behind a free registration: an
account or an e-mail address is asked for before the download. None of them
can be fetched unattended, which is why ModFileGen has no downloader.

STICS
~~~~~

Site: https://stics.inrae.fr/ (download page
https://stics.inrae.fr/telechargement).

The download needs an account on the INRAE forge: *"Téléchargez les
fichiers ici ... après vous être authentifié."* JavaSTICS is CeCILL-B, the
STICS model itself CeCILL-C.

Take the JavaSTICS package for the version you want and unpack it. One
archive carries **both platforms' simulators**, which is why no build step
is needed:

.. code-block:: text

    JavaSTICS-v11.0.0/
      bin/
        stics_modulo        <- Linux, macOS
        stics_modulo.exe    <- Windows
        jre17/              <- bundled Java, for the JavaSTICS interface

ModFileGen uses ``bin/stics_modulo`` directly and never starts the Java
interface, so the bundled ``jre17`` is not needed for a ModFileGen run.

.. note::

   As of the 11.0.0 release, the download page's own summary still
   advertises 10.5.0 while the news item announces 11.0.0. Check the file
   listing rather than the page text.

DSSAT
~~~~~

Site: https://dssat.net/, download request at
https://get.dssat.net/request/.

Free of charge, but an e-mail verification then a registration form is
required: *"The e-mail message will ask you to complete a registration form
that is required for obtaining a copy of the software."* Several versions
are offered from the same form, v4.7.5 and v4.8.x among them.

The source is also public, BSD-3-Clause, at
https://github.com/DSSAT/dssat-csm-os, and builds with CMake::

    mkdir build && cd build && cmake .. && make

The executable lands in ``bin/``. Building needs a Fortran compiler, which
is itself usually an administrator install, so the official package is the
easier route on a locked-down machine.

APSIM Next Generation
~~~~~~~~~~~~~~~~~~~~~

Registration: https://registration.apsim.info/, source at
https://github.com/APSIMInitiative/ApsimX.

A licence must be chosen before downloading: *"select the appropriate
licence type to register and download APSIM."* General Use is free for
public-good research and education; commercial use is a paid Special Use
licence. The registration page states it is *"Compatible on all major
operating systems including Windows, MacOS and Debian-based Linux
distributions"*, without saying which package format each one gets.

What ModFileGen needs from the install is the command-line program,
``Models`` (``Models.exe`` on Windows), together with the rest of the
directory it ships in -- see below.

CELSIUS and DataMill
~~~~~~~~~~~~~~~~~~~~

These are not public downloads. CELSIUS V32 is built from
https://github.com/CropModelingPlatform/CelsiusV32; CELSIUS v3 and DataMill
are distributed as prebuilt directories by the ModFileGen maintainers.

All three are .NET applications, so they need a matching .NET runtime
present on the machine. CELSIUS v3 and DataMill target ``net5.0``; a
Windows build is produced with::

    dotnet publish --configuration Release --runtime win-x64

A ``--self-contained`` publish bundles the runtime into the output
directory, which avoids asking a student to install .NET separately.

What has to sit beside the executable
-------------------------------------

For every engine but STICS, the executable alone does nothing. Copying just
the binary somewhere convenient is the most common way to get an engine
that is found and still cannot run, so ``agriscale engines`` checks for
these siblings and reports ``incomplete`` rather than ``ok``.

====================  ==============  ==========================================
Engine                Needs beside    Why
====================  ==============  ==========================================
STICS v9, v11         nothing         statically linked
DSSAT v4.7, v4.8      ``DSSATPRO.*``  the table of its data directories
APSIM NG              ``*.dll``       61 .NET assemblies
CELSIUS v3            ``*.dll``       .NET app: ``celsius.dll`` and its deps
CELSIUS V32           ``*.dll``       idem, plus its SQLite interop
DataMill              ``*.dll``       idem
====================  ==============  ==========================================

The siblings are looked for next to the *real* file, not next to a symlink
pointing at it, so a link such as ``/usr/bin/dssat`` into
``/usr/share/dssat`` is handled correctly.

DSSAT: ``DSSATPRO`` holds absolute paths
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``DSSATPRO`` is not a marker file, it is a path table, and the paths are
absolute and platform-specific. Shipped, it reads::

    *** *  DSSAT PROFILE * ***
    DDB C: \DSSAT48
    DTB C: \DSSAT48

and, in its Linux variant ``DSSATPRO.L48``::

    *** *  DSSAT PROFILE LINUX* ***
    DDB // /usr/local/share/dssat48
    DTB // /usr/local/share/dssat48

If DSSAT is unpacked anywhere other than the path written in that file, the
engine starts, finds no genotype or weather data, and fails with messages
that point at the data rather than at the configuration. **Edit
``DSSATPRO`` to match the directory you actually unpacked into.** The
container does exactly this: its ``DSSATPRO.L48`` names
``/usr/share/dssatv48``, the location it installs to, rather than the
shipped default.

Checking the result
-------------------

``agriscale engines`` again. An engine that is ready reads::

    STICS v11              ok              MODFILEGEN_STICS_V11
                                           D:\JavaSTICS-v11.0.0\bin\stics_modulo.exe

The *Found via* column is the part worth reading: it says which of the
three ways above actually answered. "I set the variable but it is found via
an install location" means the variable did not take effect, which is a
different problem from the engine being absent.

The command's exit status is 0 even when engines are missing: generating
input files needs none of them, so a missing engine must not fail a build
or a CI run.

What is not checked
-------------------

Nothing is executed. Starting a crop model to ask whether it exists would
do real work -- read files, write outputs -- so the report is deliberately
limited to what can be seen on disk. It therefore cannot tell you:

* the **version** of the binary it found. A v9 ``stics_modulo`` placed in
  the v11 directory is reported ``ok``;
* whether the binary matches the machine's architecture;
* whether its dynamic libraries resolve, or whether the required .NET
  runtime is installed.

The first simulation remains the real test.
