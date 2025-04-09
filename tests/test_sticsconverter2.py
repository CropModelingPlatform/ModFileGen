from modfilegen.Converter.SticsConverter import sticsconverter
from modfilegen import GlobalVariables
import sqlite3
from pathlib import Path
import os

data = os.path.join(Path(__file__).parent, "data")
modeldictionnary_f = os.path.join(data,"ModelsDictionaryArise.db")
masterinput_f =  os.path.join(data, "MasterInput.db")

directory_path = os.path.join(data, "output")
# create output directory if it does not exist
if not os.path.exists(directory_path):
    Path(directory_path).mkdir(parents=True, exist_ok=True)

GlobalVariables["dbModelsDictionary" ] = modeldictionnary_f     
GlobalVariables["dbMasterInput" ] = masterinput_f 
GlobalVariables["directorypath"] = directory_path   # contains the path of list of USM
GlobalVariables["pltfolder"] = os.path.join(data,"cultivars","sticsv10") # path of cultivars
GlobalVariables["nthreads"] = 4
GlobalVariables["dt"] = 0
GlobalVariables["stics"] = "v10"

def test_sticsconverter():
    sticsconverter.main()
    return 0

if __name__ == "__main__":
    test_sticsconverter()
    print("test_sticsconverter")
