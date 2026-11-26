"""STICS reports must be generated with the separator the readers expect.

``create_df_summary`` and ``create_df_daily`` parse the reports with pandas
and ``sep=";"``. That only works when ``tempopar.sti`` carries
``codeseprapport = 2``, which makes STICS separate the columns with
``separateurrapport`` instead of using fixed-width columns.

ModelsDictionary still holds 1 for that parameter, and the ``sticsrun.sh``
scripts used to patch the generated file before every run with a GNU-only
``sed -i -z``. Generating the right value removes that shell dependency, so
these tests guard what the patch used to guarantee.
"""

import pytest

from modfilegen.Converter.SticsConverter.sticsconverter import (
    common_tempopar as common_tempopar_v9,
)
from modfilegen.Converter.SticsV11Converter.sticsconverter import (
    common_tempopar as common_tempopar_v11,
)

BUILDERS = {"v9": common_tempopar_v9, "v11": common_tempopar_v11}


@pytest.mark.parametrize("version", sorted(BUILDERS))
def test_codeseprapport_is_generated_as_2(modelsdictionary_db, version):
    lines = BUILDERS[version](str(modelsdictionary_db)).splitlines()

    index = lines.index("codeseprapport")
    assert lines[index + 1] == "2"


@pytest.mark.parametrize("version", sorted(BUILDERS))
def test_the_separator_is_the_one_the_readers_split_on(
    modelsdictionary_db, version
):
    lines = BUILDERS[version](str(modelsdictionary_db)).splitlines()

    index = lines.index("separateurrapport")
    assert lines[index + 1] == ";"


@pytest.mark.parametrize("version", sorted(BUILDERS))
def test_the_model_dictionary_default_is_still_1(modelsdictionary_db, version):
    """The value is forced in code, not fixed in the data.

    If someone corrects ModelsDictionary later, this test fails and says so,
    rather than leaving two sources of truth silently disagreeing.
    """
    import sqlite3

    connection = sqlite3.connect(f"file:{modelsdictionary_db}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT IFNULL(defaultValueOtherSource, Default_Value_Datamill) "
            "FROM Variables WHERE Champ = 'codeseprapport'"
        ).fetchall()
    finally:
        connection.close()

    assert rows, "codeseprapport is missing from the Variables fixture"
    assert {str(row[0]) for row in rows} == {"1"}
