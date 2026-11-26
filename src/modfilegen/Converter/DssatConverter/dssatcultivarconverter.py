from modfilegen.converter import Converter
from sqlite3 import Connection
import os
import pandas as pd
import traceback
import re
import shutil
from modfilegen.paths import path_parts


DSSAT_CULTIVAR_SUFFIXES = {
    "v47": "047",
    "v48": "048",
}


def cultivar_code_for_version(dscrop, dssat_version):
    """Return DSCROP with the suffix matching the requested DSSAT version."""
    try:
        suffix = DSSAT_CULTIVAR_SUFFIXES[dssat_version]
    except KeyError as exc:
        supported_versions = ", ".join(DSSAT_CULTIVAR_SUFFIXES)
        raise ValueError(
            f"Unsupported DSSAT version {dssat_version!r}; expected {supported_versions}"
        ) from exc

    base_dscrop = re.sub(r"(?:047|048)$", "", str(dscrop).strip())
    return base_dscrop + suffix

#: One plant per season. DSSAT simulates a single crop at a time: it has no
#: two-layer canopy, so an association cannot be represented at all. The
#: successive converter already refuses one; this is the standard path.
_PLANTS_PER_SEASON = """
    SELECT SeasonOrder, COUNT(DISTINCT PlantOrder) AS plants
    FROM CropManagement
    WHERE idMangt = ?
    GROUP BY SeasonOrder
    HAVING plants > 1
"""


def reject_an_association(idMangt, master_input_connection):
    """Refuse a management that grows two crops at once.

    Without this the converter took whichever plant row came back first and
    wrote a single-crop simulation from it, dropping the other crop with no
    message: a plausible result that answers a different question from the
    one asked.
    """
    crowded = master_input_connection.execute(
        _PLANTS_PER_SEASON, (idMangt,)
    ).fetchall()
    if not crowded:
        return
    seasons = ", ".join(str(row[0]) for row in crowded)
    raise ValueError(
        f"DSSAT cannot simulate an association: management {idMangt!r} has "
        f"several plants in season(s) {seasons}. DSSAT grows one crop at a "
        "time; use STICS for intercropping."
    )


class DssatCultivarConverter(Converter):
    def __init__(self):
        super().__init__()

    def export(self, directory_path, master_input_connection, pltfolder, usmdir, dssat_version="v47"):
        ST = path_parts(directory_path)   
        sq = """SELECT CropManagement.idMangt as idMangt, ListCultOption.CG as crop, ListCultOption.DSCROP as dscrop 
        FROM (ListCultOption INNER JOIN (ListCultivars INNER JOIN CropManagement ON ListCultivars.IdCultivar = CropManagement.Idcultivar) ON ListCultOption.CodePSpecies = ListCultivars.CodePSpecies) where idMangt= '%s' ;"""%(ST[-1])   
        reject_an_association(ST[-1], master_input_connection)
        df_sim = pd.read_sql(sq, master_input_connection)
        rows = df_sim.to_dict('records')

        # DSSAT crop model = current crop code (CG) + model (DSCROP), e.g. MZCER047.
        cultivar_code = rows[0]["crop"] + cultivar_code_for_version(
            rows[0]["dscrop"], dssat_version
        )
        src_path_cul = os.path.join(pltfolder, cultivar_code + ".CUL")
        src_path_eco = os.path.join(pltfolder, cultivar_code + ".ECO")
        src_path_spe = os.path.join(pltfolder, cultivar_code + ".SPE")
        
        if not os.path.exists(usmdir):
            os.makedirs(usmdir)
        # copy src_path_eco to usmdir if it exists
        if os.path.exists(src_path_eco):
            shutil.copy(src_path_eco, usmdir)
        shutil.copy(src_path_cul, usmdir)
        shutil.copy(src_path_spe, usmdir)
        return rows[0]["crop"]
        #return src_path_cul, src_path_eco, src_path_spe





