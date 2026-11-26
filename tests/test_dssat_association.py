"""DSSAT refuses a management that grows two crops at once.

DSSAT simulates a single crop at a time; it has no two-layer canopy, so an
association cannot be represented. The successive converter already said so.
The standard converter did not: it took whichever plant row came back first
and wrote a single-crop simulation from an intercrop, dropping a crop with
no message. A plausible result that answers a different question is worse
than a refusal.
"""

import sqlite3

import pytest

from modfilegen.Converter.DssatConverter.dssatcultivarconverter import (
    reject_an_association,
)


@pytest.fixture
def connection(masterinput_copy):
    link = sqlite3.connect(str(masterinput_copy))
    try:
        yield link
    finally:
        link.close()


def plants(connection, idMangt):
    return connection.execute(
        "SELECT SeasonOrder, PlantOrder FROM CropManagement WHERE idMangt = ?"
        " ORDER BY SeasonOrder, PlantOrder",
        (idMangt,),
    ).fetchall()


def test_an_association_is_refused_by_name(connection):
    """Mgt1M0_135 is the fixture's intercrop: two plants in one season."""
    assert plants(connection, "Mgt1M0_135") == [(1, 1), (1, 2)]

    with pytest.raises(ValueError, match="cannot simulate an association"):
        reject_an_association("Mgt1M0_135", connection)


def test_the_refusal_names_the_management_and_the_season(connection):
    with pytest.raises(ValueError) as refusal:
        reject_an_association("Mgt1M0_135", connection)

    message = str(refusal.value)
    assert "Mgt1M0_135" in message
    assert "season(s) 1" in message
    assert "STICS" in message  # where intercropping does belong


def test_a_single_crop_management_passes(connection):
    assert plants(connection, "FERT_MIN_ORG") == [(1, 1)]

    reject_an_association("FERT_MIN_ORG", connection)


def test_a_rotation_is_not_an_association(connection):
    """Three seasons, one plant each: successive cropping, not intercropping.

    Counting the management's rows rather than its plants per season would
    reject this, which is the mistake the guard has to avoid.
    """
    assert plants(connection, "ROT_MAIZE_PEANUT_3Y") == [(1, 1), (2, 1), (3, 1)]

    reject_an_association("ROT_MAIZE_PEANUT_3Y", connection)


def test_an_unknown_management_is_not_refused(connection):
    """Absence is another converter's error to report, not this one's."""
    reject_an_association("no_such_management", connection)
