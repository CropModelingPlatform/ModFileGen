
from modfilegen.version import __version__

# Global variables
GlobalVariables = {"storeNumMinSimu" : 0,
                      "storeNumMaxSimu" : 0,
                      "storeKeyDataN" : 0,  #'variable containing value of column 'N' to read 
                                            #' Public RepSource As String = "D:\donneesFA\modelisation\Arise\dataMillArise\AppliDatamill"
                     "dbMasterInput" : "",
                    "dbModelsDictionary" : "",
                    "dbCelsius" : "",
                    "dt" : 1,
                    "ori_MI" : "",
                    "parts": 1,
                    "tempDir": "",
                    "package": "",
                    "thirdyear": 0,
                    "dailyoutput": 0,
                    "sticsv11Q0Strategy": "default",
                    # Soil albedo: "measured" (Soil.albedo) or "texture"
                    # (re-estimated from Soil.SoilTextureType).
                    "albedoStrategy": "measured",
                    # Model executables. An empty value means the per-platform
                    # default of the matching runner module. Resolve these in
                    # main() and pass the result to the workers: a loky worker
                    # re-imports this module and only ever sees the defaults
                    # here, never what the caller set.
                    "sticsV9Executable": "",
                    "sticsV11Executable": "",
                    "dssatExecutable": "",      # DSSAT v4.7
                    "dssatV48Executable": "",   # DSSAT v4.8
                    "celsiusExecutable": "",    # CELSIUS v3
                    "datamillExecutable": "",
                    "celsius_version": "v3",
                    "celsius_mode": "standard",
                    "dbCelsiusV32Template": "",
                    "celsiusV32Output": "",
                    # Empty, so modfilegen.engines runs its full cascade
                    # (PATH, then the known install locations).
                    "celsiusV32Executable": "",
                    "celsiusIdsim": None,
                    "runCelsiusV32": 1,
                    "outputVariablesConfig": None,
                    "outputSelectionsConfig": None,
                    "profileVariablesConfig": None,
                    "outputSelection": "legacy"
                     }
