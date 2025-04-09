import os

def write_apsim_met(met, wrt_dir=None, filename=None):
    """
    Writes meteorological data to an APSIM-compatible .met file.

    Parameters:
        met (dict): A dictionary containing meteorological data and metadata.
            Required keys/attributes:
                - "filename" (str): Default filename for the .met file.
                - "site" (str): Site name.
                - "latitude" (str): Latitude of the site.
                - "longitude" (str): Longitude of the site.
                - "tav" (str): Annual average temperature.
                - "amp" (str): Annual temperature amplitude.
                - "colnames" (list): List of column names for the data.
                - "units" (list): List of units for the data.
                - "comments" (str): Optional comments for the file.
                - "constants" (list): Optional constants for the file.
                - "data" (pd.DataFrame): Meteorological data in tabular format.

        wrt_dir (str, optional): Directory to save the .met file. Defaults to None.
        filename (str, optional): Name of the output .met file. Defaults to None.
    """
    # Determine the output file path
    if met.get("filename") != "noname.met" and filename is None:
        filename = met.get("filename")

    if wrt_dir is None and filename is None:
        file_path = met.get("filename")
    elif wrt_dir is not None and filename is None:
        if met.get("filename") == "noname.met":
            raise ValueError("Need to supply filename if 'wrt_dir' is not None")
        else:
            file_path = os.path.join(wrt_dir, met.get("filename"))
    elif wrt_dir is None and filename is not None:
        raise ValueError("Need to supply 'wrt_dir' if filename is not None")
    elif wrt_dir is not None and filename is not None:
        file_path = os.path.join(wrt_dir, filename)

    if filename is not None and not filename.endswith(".met"):
        raise ValueError("filename should end in .met")

    # Open the file for writing
    with open(file_path, "w") as con:
        # Write comments if they exist
        if "comments" in met and met["comments"]:
            con.write(met["comments"] + "\n")

        # Write header
        con.write("[weather.met.weather]\n")

        # Write site if it exists
        if "site" in met and met["site"]:
            con.write(met["site"] + "\n")

        # Write latitude (required)
        if "latitude" not in met or not met["latitude"]:
            raise ValueError("latitude should be present")
        con.write(met["latitude"] + "\n")

        # Write longitude if it exists
        if "longitude" in met and met["longitude"]:
            con.write(met["longitude"] + "\n")

        # Write tav and amp
        con.write(met["tav"] + "\n")
        con.write(met["amp"] + "\n")

        # Write constants if they exist
        if "constants" in met and met["constants"]:
            for constant in met["constants"]:
                con.write(constant + "\n")

        # Write column names and units
        con.write(" ".join(met["colnames"]) + "\n")
        con.write(" ".join(met["units"]) + "\n")

        # Write the data
        met["data"].to_csv(con, sep=" ", index=False, header=False)

    print(f"File saved successfully at {file_path}")
    