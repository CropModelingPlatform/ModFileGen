"""Plant and genotype files come from the user, in whatever shape.

A student points `--cultivars` at files they were given or wrote: CRLF from
Windows, LF from Linux, cp1252 from a spreadsheet, a byte-order mark from
Notepad. The converters must hand them to the engine exactly as received.

They do, because all three copy byte for byte -- STICS v9 and v11 with
shutil.copyfile, DSSAT with shutil.copy -- and never decode them. These
tests hold them to that, because routing these files through
modfilegen.text_files would look like an improvement and would be a defect:
it would normalise the line endings and raise on anything that is not UTF-8.
"""

import re
import shutil
import sqlite3
from pathlib import Path

import pytest

from modfilegen.Converter.DssatConverter.dssatcultivarconverter import (
    DssatCultivarConverter,
)
from modfilegen.Converter.SticsV11Converter.sticsficplt1converter import (
    SticsFicplt1Converter,
)

#: What a user may plausibly hand over. Each is bytes, so nothing here
#: decides an encoding on their behalf.
SHAPES = {
    "lf": b"codeplante\nmai\nhautmax\n2.5\n",
    "crlf": b"codeplante\r\nmai\r\nhautmax\r\n2.5\r\n",
    "cp1252": "codeplante\nma\xefs\nhautmax\n2.5\n".encode("cp1252"),
    "utf8-bom": "﻿codeplante\nmais\nhautmax\n2.5\n".encode("utf-8"),
    "no-final-newline": b"codeplante\nmai\nhautmax\n2.5",
    "mixed": b"codeplante\r\nmai\nhautmax\r\n2.5\n",
}


@pytest.fixture
def connection(masterinput_copy):
    link = sqlite3.connect(str(masterinput_copy))
    # One season, as the successive converter exposes to these writers.
    link.execute(
        "DELETE FROM CropManagement WHERE NOT"
        " (idMangt = 'ROT_MAIZE_PEANUT_3Y' AND SeasonOrder = 1)"
    )
    link.commit()
    try:
        yield link
    finally:
        link.close()


def plant_file_name(connection):
    """What the database says this season's plant file is called."""
    return connection.execute(
        "SELECT o.FicPlt FROM ListCultOption o"
        " JOIN ListCultivars l ON l.CodePSpecies = o.CodePSpecies"
        " JOIN CropManagement c ON c.Idcultivar = l.IdCultivar"
        " WHERE c.idMangt = 'ROT_MAIZE_PEANUT_3Y'"
    ).fetchone()[0]


# --- STICS ----------------------------------------------------------------


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_stics_hands_the_plant_file_over_unchanged(shape, connection, tmp_path):
    raw = SHAPES[shape]
    pltfolder = tmp_path / "cultivars"
    pltfolder.mkdir()
    (pltfolder / plant_file_name(connection)).write_bytes(raw)
    usmdir = tmp_path / "usm"
    usmdir.mkdir()
    directory = "tmp/5.925_6.025_2000_ROT_MAIZE_PEANUT_3Y_2/5.925_6.025/2000"

    SticsFicplt1Converter().export(directory, connection, str(pltfolder), str(usmdir))

    assert (usmdir / "ficplt1.txt").read_bytes() == raw


# --- DSSAT ----------------------------------------------------------------


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_dssat_hands_the_genotype_files_over_unchanged(shape, connection, tmp_path):
    raw = SHAPES[shape]
    pltfolder = tmp_path / "cultivars"
    pltfolder.mkdir()
    for suffix in ("CUL", "ECO", "SPE"):
        (pltfolder / f"MZCER048.{suffix}").write_bytes(raw)
    usmdir = tmp_path / "usm"
    directory = "tmp/5.925_6.025_2000_ROT_MAIZE_PEANUT_3Y_2/ROT_MAIZE_PEANUT_3Y"

    DssatCultivarConverter().export(
        directory, connection, str(pltfolder), str(usmdir), "v48"
    )

    for suffix in ("CUL", "ECO", "SPE"):
        assert (usmdir / f"MZCER048.{suffix}").read_bytes() == raw


# --- and that it stays that way -------------------------------------------


COPIERS = (
    "src/modfilegen/Converter/SticsConverter/sticsficplt1converter.py",
    "src/modfilegen/Converter/SticsV11Converter/sticsficplt1converter.py",
    "src/modfilegen/Converter/DssatConverter/dssatcultivarconverter.py",
)


@pytest.mark.parametrize("module", COPIERS)
def test_a_user_file_is_copied_and_never_decoded(module):
    """`open()` on one of these would normalise the line endings and raise
    on anything that is not UTF-8. A byte copy cannot."""
    root = Path(__file__).parent.parent
    source = (root / module).read_text(encoding="utf-8")

    assert re.search(r"shutil\.copy(file)?\(", source), (
        f"{module} no longer copies the user's file"
    )
    offenders = [
        line.strip()
        for line in source.splitlines()
        if re.search(r"\bopen\(", line) and not line.strip().startswith("#")
    ]
    assert not offenders, (
        f"{module} opens a file; user plant files must be copied, not read:\n"
        + "\n".join(offenders)
    )
