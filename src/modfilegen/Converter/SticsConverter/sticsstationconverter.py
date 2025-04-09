from modfilegen.converter import Converter
from sqlite3 import Connection
import os
import pandas as pd

class SticsStationConverter(Converter):
    def __init__(self):
        super().__init__()

    def export(self, directory_path, ModelDictionary_Connection, master_input_connection, rap, var, prof, usmdir, sticsv):
        file_name = "station.txt"
        fileContent = ""
        ST = directory_path.split(os.sep)
        T = "Select  Champ, Default_Value_Datamill, defaultValueOtherSource, IFNULL([defaultValueOtherSource],  [Default_Value_Datamill]) As dv From Variables Where ((model = 'stics') And ([Table] = 'st_station'));"
        DT = pd.read_sql_query(T,ModelDictionary_Connection)
        fetchAllQuery = """SELECT SimUnitList.idsim, Coordinates.altitude, Coordinates.latitudeDD FROM Coordinates INNER JOIN SimUnitList ON Coordinates.idPoint = SimUnitList.idPoint Where idsim ='%s';"""%(ST[-3])
        DA = pd.read_sql_query(fetchAllQuery, master_input_connection)
        rows = DA.to_dict(orient='records')
    

        sql_check = """SELECT SimUnitList.idsim, SimUnitList.idMangt FROM CropManagement INNER JOIN SimUnitList ON CropManagement.idMangt = SimUnitList.idMangt where idSim= '%s' ;"""%(ST[-3])
        DA2 = pd.read_sql_query(sql_check, master_input_connection)
        rows2 = DA2.to_dict(orient='records')


        for row in rows:
            fileContent += self.FormatSticsData(DT, "zr", 0)
            fileContent += self.FormatSticsData(DT, "NH3ref",5)
            if sticsv == "v10":
                fileContent += self.FormatSticsData(DT, "concrr", 2)
            fileContent += "latitude\n"
            # format row["latitudeDD" with precision 7
            fileContent += "{:.7f}".format(row["latitudeDD"]) + "\n"
            fileContent += self.FormatSticsData(DT, "patm")
            fileContent += self.FormatSticsData(DT, "aclim", 6)
            if len(rows2) == 1: fileContent += self.FormatSticsData(DT, "codeetp", 0)
            elif len(rows2) == 2: 
                fileContent += "codeetp\n3\n"
            fileContent += self.FormatSticsData(DT, "alphapt")
            fileContent += self.FormatSticsData(DT, "codeclichange", 0)
            fileContent += self.FormatSticsData(DT, "codaltitude", 0)
            fileContent += self.FormatSticsData(DT, "altistation")
            #'FormatSticsData(fileContent, DT, "altisimul")
            fileContent += "altisimul\n"
            if row["altitude"] is None:
                fileContent += "-99\n"
            else:
                fileContent += "{:.5f}".format(row["altitude"]) + "\n"

            fileContent += self.FormatSticsData(DT, "gradtn")
            fileContent += self.FormatSticsData(DT, "gradtx")
            fileContent += self.FormatSticsData(DT, "altinversion")
            fileContent += self.FormatSticsData(DT, "gradtninv")
            fileContent += self.FormatSticsData(DT, "cielclair")
            fileContent += self.FormatSticsData(DT, "codadret", 0)
            fileContent += self.FormatSticsData(DT, "ombragetx")
            fileContent += self.FormatSticsData(DT, "ra")
            fileContent += self.FormatSticsData(DT, "albveg")
            fileContent += self.FormatSticsData(DT, "aangst")
            fileContent += self.FormatSticsData(DT, "bangst")
            fileContent += self.FormatSticsData(DT, "corecTrosee")
            fileContent += self.FormatSticsData(DT, "codecaltemp",0)
            fileContent += self.FormatSticsData(DT, "codernet",0)
            fileContent += self.FormatSticsData(DT, "coefdevil")
            fileContent += self.FormatSticsData(DT, "aks")
            fileContent += self.FormatSticsData(DT, "bks")
            fileContent += self.FormatSticsData(DT, "cvent")
            fileContent += self.FormatSticsData(DT, "phiv0")
            fileContent += self.FormatSticsData(DT, "coefrnet")
            if sticsv == "v10":
                pass
                '''fileContent += self.FormatSticsData( DT, "codemodlsnow", 0)
                fileContent += self.FormatSticsData( DT, "tsmax")
                fileContent += self.FormatSticsData( DT, "trmax")
                fileContent += self.FormatSticsData( DT, "DKmax")
                fileContent += self.FormatSticsData( DT, "Kmin")
                fileContent += self.FormatSticsData( DT, "Tmf")
                fileContent += self.FormatSticsData( DT, "SWrf")
                fileContent += self.FormatSticsData( DT, "Pns")
                fileContent += self.FormatSticsData( DT, "E")
                fileContent += self.FormatSticsData( DT, "prof")
                fileContent += self.FormatSticsData( DT, "tminseuil")
                fileContent += self.FormatSticsData( DT, "tmaxseuil")'''
        station = fileContent
        try:
            # Exporter le fichier vers le répertoire spécifié
            self.write_file(usmdir, file_name, fileContent)
        except Exception as e:
            print(f"Error during writing file : {e}")

        file_name = "snow_variables.txt"
        fileContent = ""
        fileContent += "   0.00000000       0.00000000       0.00000000       0.00000000 "
        fileContent += "\n"
        snow = fileContent
        try:
            # Exporter le fichier vers le répertoire spécifié
            self.write_file(usmdir, file_name, fileContent)
        except Exception as e:
            print(f"Error during writing file : {e}")
        file_name = "prof.mod"
        fileContent = prof
        try:
            # Exporter le fichier vers le répertoire spécifié
            self.write_file(usmdir, file_name, fileContent)
        except Exception as e:
            print(f"Error during writing file : {e}")
        file_name = "rap.mod"
        fileContent = rap
        try:
            # Exporter le fichier vers le répertoire spécifié
            self.write_file(usmdir, file_name, fileContent)
        except Exception as e:
            print(f"Error during writing file : {e}")
        file_name = "var.mod"
        fileContent = var
        try:
            # Exporter le fichier vers le répertoire spécifié
            self.write_file(usmdir, file_name, fileContent)
        except Exception as e:
            print(f"Error during writing file : {e}")
        return [station, snow]

    def  FormatSticsData(self, row ,champ, precision = 5, fieldIt = 0):
        res = ""
        typedata = ""
        data = None
        file_content = ""
        fieldName = champ
        # For repeated fields, build field name
        if fieldIt != 0:
            champ = champ + str(fieldIt) 
        # Fetch data
        rw = row[row['Champ'] == champ]
        data = rw["dv"].values[0]
        res = ""
        # If type is string or int
        if isinstance(data, str) or isinstance(data, int):
            res = str(data)
        data = float(data)
        # If type is real
        if isinstance(data, float):
            tmp = float(data)
            if precision is None or precision==0:
                res = "{:.0f}".format(tmp)
            elif 1 < precision < 7:
                res = "{:.{}f}".format(tmp, precision)
            else:
                res = "{:0.3e}".format(tmp)
        # If cell is null
        if data is None:
            res = ""
        # Print data in file
        file_content += fieldName + "\n"
        file_content += res + "\n"
        return file_content
