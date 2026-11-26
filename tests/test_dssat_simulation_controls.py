"""One SIMULATION CONTROLS block per distinct set of controls.

DSSAT numbers a whole block at once -- GENERAL, OPTIONS, METHODS,
MANAGEMENT, OUTPUTS and AUTOMATIC MANAGEMENT all carry the same number --
and a treatment's ``SM`` column points at it. So two crop-seasons needing
one different value need two blocks. DSSAT's own UFGA7803.SQX does exactly
that: four treatments, two blocks, soybean and dry bean sharing the first
and both fallows the second.

Before this, the writer emitted the first rotation's block only and set
every ``SM`` to 1, so a rotation could not carry two different values at
all.
"""

import pytest

from modfilegen.Converter.DssatConverter.dssatsuccessiveconverter import (
    simulation_control_blocks,
)


class Rotation:
    """Just enough of a rotation for the grouping."""

    def __init__(self, index, body):
        self.index = index
        self.row = {"idsim": f"sim-{index}"}
        self.sections = {"*SIMULATION": ["*SIMULATION CONTROLS", *body]}


def block(number, photo="R", sdate="00120"):
    return [
        f"{number:2d} GE              1     1     S {sdate}  2150 CSM335",
        f"{number:2d} OP              Y     N     N     N     N",
        f"{number:2d} ME              M     M     E     R     S     {photo}",
    ]


def test_identical_controls_make_one_block():
    rotations = [Rotation(i, block(1)) for i in (1, 2, 3)]

    blocks, numbers = simulation_control_blocks(rotations, nyers=3, sequence_start="00120")

    assert len(blocks) == 1
    assert numbers == {1: 1, 2: 1, 3: 1}


def test_a_differing_value_makes_a_second_block():
    """MEPHO is R for a CERES maize and C or L for a CROPGRO peanut."""
    rotations = [
        Rotation(1, block(1, photo="R")),
        Rotation(2, block(1, photo="L")),
        Rotation(3, block(1, photo="R")),
    ]

    blocks, numbers = simulation_control_blocks(rotations, nyers=3, sequence_start="00120")

    assert len(blocks) == 2
    # The third crop-season reuses the first block, as UFGA7803.SQX does.
    assert numbers == {1: 1, 2: 2, 3: 1}


def test_a_field_the_emission_rewrites_is_not_a_difference():
    """Each rotation carries its own SDATE, which emission overwrites.

    The first attempt grouped nothing because of this: three rotations
    differing only on a field about to be replaced came out as three
    identical blocks.
    """
    rotations = [
        Rotation(1, block(1, sdate="00120")),
        Rotation(2, block(1, sdate="01140")),
        Rotation(3, block(1, sdate="02150")),
    ]

    blocks, _ = simulation_control_blocks(rotations, nyers=3, sequence_start="00120")

    assert len(blocks) == 1


def test_the_block_number_is_not_a_difference():
    """Sections are generated numbered 1; the number is assigned here."""
    rotations = [Rotation(1, block(1)), Rotation(2, block(2))]

    blocks, _ = simulation_control_blocks(rotations, nyers=3, sequence_start="00120")

    assert len(blocks) == 1


def test_a_missing_section_is_reported_with_its_simulation():
    rotation = Rotation(1, block(1))
    rotation.sections = {}

    with pytest.raises(ValueError, match="sim-1"):
        simulation_control_blocks([rotation], nyers=3, sequence_start="00120")
