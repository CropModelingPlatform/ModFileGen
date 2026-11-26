"""The AUTOMATIC MANAGEMENT section, and the planting window in it.

DSSAT reads SIMULATION CONTROLS level by level. With one level it tolerates
a level that has no AUTOMATIC MANAGEMENT section; with several it fails --
error 5010, key IPSIM, at the next level's GENERAL line -- so a rotation
needing two different control blocks could not start at all. The section is
therefore written for every level, whatever the MANAGEMENT switches say,
as DSSAT's own sequence examples do.

Writing it always exposed a defect that had been hidden by how rarely it
appeared: the planting window came out as `005161 014810`, two dates run
together and neither of them a date.
"""

import re
from pathlib import Path

import pytest

from modfilegen.Converter.DssatConverter import dssatxconverter
from modfilegen.Converter.DssatConverter.dssatxconverter import (
    planting_window_date,
)


# --- the planting window ---------------------------------------------------


def test_a_template_yyddd_default_keeps_only_its_day():
    """The dictionary holds PWDINF 5161 and PWDINL 5175: yyddd dates from a
    workspace whose year was 05, not days of year. Prefixing them with the
    simulation's year gave six digits in a six-wide field."""
    assert planting_window_date(5161, 2000) == "00161"
    assert planting_window_date(5175, 2000) == "00175"


def test_a_plain_day_of_year_works_too():
    """Both spellings have to resolve the same, since a user may write
    either and 161 and 5161 mean the same day."""
    assert planting_window_date(161, 2000) == planting_window_date(5161, 2000)
    assert planting_window_date(5, 2000) == "00005"


def test_the_simulation_s_own_year_is_used():
    assert planting_window_date(5161, 2001) == "01161"
    assert planting_window_date(5161, 1998) == "98161"


def test_a_window_past_new_year_rolls_over():
    """Day 400 of 2000 is day 35 of 2001."""
    assert planting_window_date(400, 2000) == "01035"


def test_the_value_may_arrive_as_a_string():
    assert planting_window_date("5161", "2000") == "00161"


def test_the_result_is_always_five_characters():
    """It goes into a six-wide field beside another date; six digits made
    the two run together."""
    for value in (1, 5, 161, 365, 5161, 5175):
        assert len(planting_window_date(value, 2000)) == 5


# --- the section is unconditional -----------------------------------------


def test_the_section_is_written_whatever_the_switches_say():
    """The gate was `if Dv_planting=="A" or ...`, and the fixture's
    management switches are R and M, so no level ever got the section.

    Checked against the source: exercising it needs the whole dictionary
    and an engine, which the integration run covers.
    """
    source = Path(dssatxconverter.__file__).read_text(encoding="utf-8")
    gate = re.search(
        r'if Dv_planting\s*==\s*"A"[^\n]*:\s*\n\s*fileContent \+= "@  AUTOMATIC',
        source,
    )

    assert gate is None, (
        "the AUTOMATIC MANAGEMENT section is gated again; DSSAT needs it on "
        "every SIMULATION CONTROLS level"
    )
    assert '"@  AUTOMATIC MANAGEMENT"' in source


def test_the_planting_window_no_longer_prefixes_a_whole_date():
    """The shape of the original defect, so it cannot come back."""
    source = Path(dssatxconverter.__file__).read_text(encoding="utf-8")

    assert 'format(int(Dv), "03")' not in source
