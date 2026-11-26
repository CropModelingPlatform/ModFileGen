"""What DSSAT can and cannot be asked to simulate.

Two kinds of management are outside DSSAT's reach, and both used to be lost
rather than reported:

*Associations.* DSSAT grows one crop at a time; it has no two-layer canopy.
The standard converter took whichever plant row came back first and wrote a
single-crop simulation from an intercrop, dropping the other crop in
silence.

*Rotations, in standard mode.* A management with several seasons belongs to
the successive converter, which carries soil state from one season to the
next. Standard mode simulated season 1 and ignored the rest, equally
quietly -- so a maize-peanut-maize rotation came back as one maize.

Both are now refused by name. ``NotApplicable`` is the distinction the
caller needs: it says "outside this model's domain", not "something broke",
so a run can decline work and still be reported as having succeeded.
"""

__all__ = [
    "NotApplicable",
    "reject_an_association",
    "reject_a_rotation",
    "check",
    "survey",
]


class NotApplicable(ValueError):
    """The simulation is outside DSSAT's domain. Not a defect.

    Derived from ValueError, which is what the converters already raised
    and catch, so existing handling keeps working unchanged.
    """


_CROWDED_SEASONS = """
    SELECT SeasonOrder, COUNT(DISTINCT PlantOrder) AS plants
    FROM CropManagement
    WHERE idMangt = ?
    GROUP BY SeasonOrder
    HAVING plants > 1
"""

_SEASONS = """
    SELECT COUNT(DISTINCT SeasonOrder)
    FROM CropManagement
    WHERE idMangt = ?
"""


def reject_an_association(idMangt, master_input_connection):
    """Refuse a management that grows two crops at once."""
    crowded = master_input_connection.execute(
        _CROWDED_SEASONS, (idMangt,)
    ).fetchall()
    if not crowded:
        return
    seasons = ", ".join(str(row[0]) for row in crowded)
    raise NotApplicable(
        f"DSSAT cannot simulate an association: management {idMangt!r} has "
        f"several plants in season(s) {seasons}. DSSAT grows one crop at a "
        "time; use STICS for intercropping."
    )


def reject_a_rotation(idMangt, master_input_connection):
    """Refuse a multi-season management in standard mode.

    Standard mode has nowhere to carry the soil state between seasons, so
    the seasons after the first were simply never simulated.
    """
    (seasons,) = master_input_connection.execute(_SEASONS, (idMangt,)).fetchone()
    if seasons <= 1:
        return
    raise NotApplicable(
        f"DSSAT standard mode cannot simulate a rotation: management "
        f"{idMangt!r} has {seasons} seasons, and only the first would be "
        "simulated. Use --mode successive, which carries the soil state "
        "from one season to the next."
    )


def check(idMangt, master_input_connection, mode="standard"):
    """Every applicability rule for ``mode``, in the order they are cheap."""
    reject_an_association(idMangt, master_input_connection)
    if mode == "standard":
        reject_a_rotation(idMangt, master_input_connection)


#: One row per crop-season actually asked for: a SimUnitList row times the
#: plants and seasons of its management. Counting SimUnitList rows alone
#: understates the work by more than half on a fixture with one intercrop
#: and one rotation.
_CROP_SEASONS = """
    SELECT SimUnitList.idsim, CropManagement.idMangt
    FROM SimUnitList
    JOIN CropManagement ON CropManagement.idMangt = SimUnitList.idMangt
"""


def survey(master_input_connection, mode="standard"):
    """How many crop-seasons are asked for, and how many DSSAT can run.

    Answered without running anything, so a caller can state up front what
    it expects and afterwards tell a declined simulation from a lost one.
    """
    requested = 0
    applicable = 0
    declined = {}
    for idsim, idMangt in master_input_connection.execute(_CROP_SEASONS):
        requested += 1
        try:
            check(idMangt, master_input_connection, mode)
        except NotApplicable as reason:
            declined.setdefault(str(reason), 0)
            declined[str(reason)] += 1
        else:
            applicable += 1
    return {
        "requested": requested,
        "applicable": applicable,
        "declined": declined,
    }
