"""The residues block, when organic matter is applied more than once.

`if dataTable["idresidueDssat"].values:` asks numpy for the truth of a whole
column. With one residue row it happens to work; with two it raises, so no
management applying organic matter twice could be converted at all. The
fixture's FERT_MIN_ORG applies manure twice, which is how this surfaced.
"""

import sqlite3

import pytest

from modfilegen.Converter.DssatConverter.dssatxconverter import writeBlockResidues


@pytest.fixture
def connections(masterinput_copy, modelsdictionary_db):
    master = sqlite3.connect(str(masterinput_copy))
    dictionary = sqlite3.connect(str(modelsdictionary_db))
    try:
        yield master, dictionary
    finally:
        master.close()
        dictionary.close()


def residue_rows(master, idsim):
    """How many residue applications the simulation carries."""
    return master.execute(
        """SELECT COUNT(*)
           FROM SimUnitList
           JOIN CropManagement ON CropManagement.idMangt = SimUnitList.idMangt
           JOIN OrganicFOperations
                ON OrganicFOperations.OFertiPolicyCode
                   = CropManagement.OFertiPolicyCode
           WHERE SimUnitList.idsim = ?""",
        (idsim,),
    ).fetchone()[0]


def test_two_residue_applications_are_written(connections):
    master, dictionary = connections
    idsim = "5.925_6.025_2001_FERT_MIN_ORG_2"
    assert residue_rows(master, idsim) >= 2, "the fixture must apply manure twice"

    block = writeBlockResidues("dssat_x_residues", idsim, "dssat_x_exp_id", dictionary, master)

    assert "*RESIDUES AND ORGANIC FERTILIZER" in block
    # One header line plus one line per application.
    lines = [line for line in block.splitlines() if line.strip()]
    assert len(lines) >= 4


def test_each_line_carries_its_own_residue_code(connections):
    """The bug tested the whole column's truth, not the row being written."""
    master, dictionary = connections

    block = writeBlockResidues(
        "dssat_x_residues", "5.925_6.025_2001_FERT_MIN_ORG_2", "dssat_x_exp_id",
        dictionary, master
    )

    data = [
        line for line in block.splitlines()
        if line.strip() and not line.startswith(("*", "@"))
    ]
    assert len(data) == 2, data
    # Column RCOD, third field: a code on every line, not blanks.
    codes = [line.split()[2] for line in data]
    assert all(code.strip() for code in codes), codes
    assert len(set(codes)) == 1, "both applications use the same residue type"
