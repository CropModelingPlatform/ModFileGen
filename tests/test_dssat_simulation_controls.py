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
    automatic_switches,
    merge_simulation_controls,
    simulation_control_blocks,
    with_inert_windows,
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

    blocks, numbers = simulation_control_blocks(
        rotations, nyers=3, sequence_start="00120", sequence_end="02350"
    )

    assert len(blocks) == 1
    assert numbers == {1: 1, 2: 1, 3: 1}


def test_a_differing_value_makes_a_second_block():
    """MEPHO is R for a CERES maize and C or L for a CROPGRO peanut."""
    rotations = [
        Rotation(1, block(1, photo="R")),
        Rotation(2, block(1, photo="L")),
        Rotation(3, block(1, photo="R")),
    ]

    blocks, numbers = simulation_control_blocks(
        rotations, nyers=3, sequence_start="00120", sequence_end="02350"
    )

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

    blocks, _ = simulation_control_blocks(
        rotations, nyers=3, sequence_start="00120", sequence_end="02350"
    )

    assert len(blocks) == 1


def test_the_block_number_is_not_a_difference():
    """Sections are generated numbered 1; the number is assigned here."""
    rotations = [Rotation(1, block(1)), Rotation(2, block(2))]

    blocks, _ = simulation_control_blocks(
        rotations, nyers=3, sequence_start="00120", sequence_end="02350"
    )

    assert len(blocks) == 1


def test_a_missing_section_is_reported_with_its_simulation():
    rotation = Rotation(1, block(1))
    rotation.sections = {}

    with pytest.raises(ValueError, match="sim-1"):
        simulation_control_blocks(
            [rotation], nyers=3, sequence_start="00120", sequence_end="02350"
        )


# --- the automatic windows are not a difference ---------------------------


def automatic(number, planting="00161 00175", harvest="01139"):
    return [
        f"{number:2d} PL          {planting}    40   100    30    40    10",
        f"{number:2d} HA              0 {harvest}   100     0",
    ]


def test_two_seasons_of_the_same_crop_share_one_block():
    """R1 and R3 of the maize-peanut-maize rotation differed on PL and HA
    only -- the year of the planting window and the end of the harvest
    window -- while every control element was identical. They took a block
    each for nothing."""
    rotations = [
        Rotation(1, block(1) + automatic(1, "00161 00175", "01139")),
        Rotation(2, block(1) + automatic(1, "01161 01175", "02149")),
        Rotation(3, block(1) + automatic(1, "02161 02175", "02350")),
    ]

    blocks, numbers = simulation_control_blocks(
        rotations, nyers=3, sequence_start="00120", sequence_end="02350"
    )

    assert len(blocks) == 1
    assert numbers == {1: 1, 2: 1, 3: 1}


def test_a_real_control_difference_still_splits_them():
    """What UFGA7803.SQX does: two blocks, the third treatment reusing the
    first, because only the second's controls differ."""
    rotations = [
        Rotation(1, block(1, photo="R") + automatic(1, "00161 00175", "01139")),
        Rotation(2, block(1, photo="L") + automatic(1, "01161 01175", "02149")),
        Rotation(3, block(1, photo="R") + automatic(1, "02161 02175", "02350")),
    ]

    blocks, numbers = simulation_control_blocks(
        rotations, nyers=3, sequence_start="00120", sequence_end="02350"
    )

    assert len(blocks) == 2
    assert numbers == {1: 1, 2: 2, 3: 1}


def test_the_planting_window_keeps_its_days():
    """Only the year is carried over. Replacing a bound outright opened the
    window on the simulation's start date instead -- 00120 for 00161.

    Checked on what is emitted: the grouping keeps the bodies as generated
    and normalises them when writing, so that any member of a group can
    stand for it.
    """
    rotations = [Rotation(1, block(1) + automatic(1, "02161 02175", "02350"))]

    emitted = merge_simulation_controls(
        rotations, nyers=3, sequence_start="00120", sequence_end="02350"
    )
    planting = next(line for line in emitted if " PL " in line)

    assert "00161 00175" in planting


def test_the_harvest_window_closes_at_the_sequence_end():
    rotations = [Rotation(1, block(1) + automatic(1, "00161 00175", "01139"))]

    emitted = merge_simulation_controls(
        rotations, nyers=3, sequence_start="00120", sequence_end="02350"
    )
    harvest = next(line for line in emitted if " HA " in line)

    assert "02350" in harvest
    assert "01139" not in harvest


def test_the_emitted_blocks_are_numbered_from_one():
    rotations = [
        Rotation(1, block(1, photo="R") + automatic(1)),
        Rotation(2, block(1, photo="L") + automatic(1)),
    ]

    emitted = merge_simulation_controls(
        rotations, nyers=3, sequence_start="00120", sequence_end="02350"
    )
    methods = [line for line in emitted if " ME " in line]

    assert [line.split()[0] for line in methods] == ["1", "2"]


# --- a window only yields while its switch leaves it unused ---------------


def management(number, plant="R", harvs="R"):
    return [
        "@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS",
        f"{number:2d} MA              {plant}     N     R     N     {harvs}",
    ]


def test_the_switches_are_read_by_position():
    switches = automatic_switches(management(1, plant="A", harvs="M"))

    assert switches["PLANT"] == "A"
    assert switches["HARVS"] == "M"
    assert switches["IRRIG"] == "N"


def test_an_automatic_planting_window_is_left_alone():
    """With PLANT = A the window is a real instruction, not structure. Its
    per-season dates stand, and two seasons that plant in different years
    then take a block each -- which is the right answer."""
    body = management(1, plant="A") + automatic(1, "02161 02175", "02350")

    kept = with_inert_windows(body, "00120", "02350")

    assert "02161 02175" in next(line for line in kept if " PL " in line)


def test_an_automatic_harvest_window_is_left_alone():
    body = management(1, harvs="A") + automatic(1, "00161 00175", "01139")

    kept = with_inert_windows(body, "00120", "02350")

    assert "01139" in next(line for line in kept if " HA " in line)


def test_harvest_at_maturity_does_not_use_the_window():
    """HARVS = M ends the run at maturity, so the window stays structure."""
    body = management(1, harvs="M") + automatic(1, "00161 00175", "01139")

    rewritten = with_inert_windows(body, "00120", "02350")

    assert "02350" in next(line for line in rewritten if " HA " in line)


def test_automatic_seasons_keep_a_block_each():
    """The end-to-end consequence: turn PLANT to A and the grouping stops
    collapsing seasons that plant on different years."""
    rotations = [
        Rotation(index, block(1) + management(1, plant="A")
                 + automatic(1, f"0{index - 1}161 0{index - 1}175", "02350"))
        for index in (1, 2, 3)
    ]

    blocks, numbers = simulation_control_blocks(
        rotations, nyers=3, sequence_start="00120", sequence_end="02350"
    )

    assert len(blocks) == 3
    assert numbers == {1: 1, 2: 2, 3: 3}


def test_inert_seasons_still_share_one_block():
    """The same rotations with PLANT left at R: nothing differs, one block."""
    rotations = [
        Rotation(index, block(1) + management(1)
                 + automatic(1, f"0{index - 1}161 0{index - 1}175", "02350"))
        for index in (1, 2, 3)
    ]

    blocks, numbers = simulation_control_blocks(
        rotations, nyers=3, sequence_start="00120", sequence_end="02350"
    )

    assert len(blocks) == 1
    assert numbers == {1: 1, 2: 1, 3: 1}
