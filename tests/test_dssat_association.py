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

from modfilegen.Converter.DssatConverter import applicability
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


# --- rotations in standard mode -------------------------------------------


def test_a_rotation_is_refused_in_standard_mode(connection):
    """Standard mode simulated season 1 and dropped the rest in silence.

    ROT_MAIZE_PEANUT_3Y is maize, then peanut, then maize. It came back as
    one maize, with nothing said about the two missing seasons.
    """
    with pytest.raises(applicability.NotApplicable, match="cannot simulate a rotation"):
        applicability.check("ROT_MAIZE_PEANUT_3Y", connection, "standard")


def test_the_rotation_refusal_points_at_successive_mode(connection):
    with pytest.raises(applicability.NotApplicable) as refusal:
        applicability.reject_a_rotation("ROT_MAIZE_PEANUT_3Y", connection)

    message = str(refusal.value)
    assert "3 seasons" in message
    assert "--mode successive" in message


def test_a_rotation_is_allowed_in_successive_mode(connection):
    """Which is the mode that carries soil state between seasons."""
    applicability.check("ROT_MAIZE_PEANUT_3Y", connection, "successive")


def test_an_association_is_refused_in_both_modes(connection):
    for mode in ("standard", "successive"):
        with pytest.raises(applicability.NotApplicable):
            applicability.check("Mgt1M0_135", connection, mode)


def test_declining_is_not_a_defect(connection):
    """The distinction a caller needs: out of domain, not broken.

    It stays a ValueError so the converters' existing handling is unchanged.
    """
    assert issubclass(applicability.NotApplicable, ValueError)


# --- the survey -----------------------------------------------------------


def test_the_survey_counts_crop_seasons_not_rows(connection):
    """Five SimUnitList rows ask for ten crop-seasons: three intercrops of
    two plants, a three-season rotation, and one plain simulation."""
    rows = connection.execute("SELECT COUNT(*) FROM SimUnitList").fetchone()[0]

    counts = applicability.survey(connection, "standard")

    assert rows == 5
    assert counts["requested"] == 10


def test_the_survey_separates_what_can_run_from_what_cannot(connection):
    counts = applicability.survey(connection, "standard")

    assert counts["applicable"] == 1
    assert sum(counts["declined"].values()) == 9
    assert counts["applicable"] + sum(counts["declined"].values()) == 10


def test_successive_mode_can_take_on_the_rotation(connection):
    standard = applicability.survey(connection, "standard")
    successive = applicability.survey(connection, "successive")

    assert successive["applicable"] == standard["applicable"] + 3
    assert sum(successive["declined"].values()) == 6  # the associations only


def test_the_survey_groups_declines_by_reason(connection):
    counts = applicability.survey(connection, "standard")

    reasons = sorted(counts["declined"])
    assert len(reasons) == 2
    assert any("association" in reason for reason in reasons)
    assert any("rotation" in reason for reason in reasons)
