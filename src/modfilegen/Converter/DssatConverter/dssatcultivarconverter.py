from modfilegen.converter import Converter
from sqlite3 import Connection
import os
import pandas as pd
import traceback
import shutil

class DssatCultivarConverter(Converter):
    def __init__(self):
        super().__init__()

    def export(self, directory_path, master_input_connection, pltfolder, usmdir, dssatv):
        ST = directory_path.split(os.sep)   
        sq = """SELECT CropManagement.idMangt as idMangt, ListCultOption.PRCROP as crop 
        FROM (ListCultOption INNER JOIN (ListCultivars INNER JOIN CropManagement ON ListCultivars.IdCultivar = CropManagement.Idcultivar) ON ListCultOption.CodePSpecies = ListCultivars.CodePSpecies) where idMangt= '%s' ;"""%(ST[-1])   
        df_sim = pd.read_sql(sq, master_input_connection)
        rows = df_sim.to_dict('records')
        if dssatv == "v47":
            src_path_cul = os.path.join(pltfolder, rows[0]["crop"]+"CER047.CUL")
            src_path_eco = os.path.join(pltfolder, rows[0]["crop"]+"CER047.ECO")
            src_path_spe = os.path.join(pltfolder, rows[0]["crop"]+"CER047.SPE")
        else:
            src_path_cul = os.path.join(pltfolder, rows[0]["crop"]+"CER048.CUL")
            src_path_eco = os.path.join(pltfolder, rows[0]["crop"]+"CER048.ECO")
            src_path_spe = os.path.join(pltfolder, rows[0]["crop"]+"CER048.SPE")
        
        if not os.path.exists(usmdir):
            os.makedirs(usmdir)
        # copy src_path_eco to usmdir if it exists
        if os.path.exists(src_path_eco):
            shutil.copy(src_path_eco, usmdir)
        shutil.copy(src_path_cul, usmdir)
        shutil.copy(src_path_spe, usmdir)
        return rows[0]["crop"]
        #return src_path_cul, src_path_eco, src_path_spe





