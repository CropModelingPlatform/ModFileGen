-- Saturated hydraulic conductivity as a measured soil property.
--
-- Unit: cm/h, as DSSAT SSKS (SOIL.CDE: "Sat. hydraulic conductivity,
-- macropore, cm h-1"). APSIM KS is in mm/day: 1 cm/h = 240 mm/day.
--
-- Soil.Ssks describes a 'simple' soil (its single layer) and is the fallback
-- of a detailed soil; SoilLayers.Ssks describes one layer. NULL means not
-- measured: converters then use an explicit SoilParameterOverrides value,
-- else the ModelsDictionary default (DSSAT ssks) or the APSIM legacy KS
-- (20 mm/day). An explicit override always wins over a measured value.
--
-- Apply each statement only when PRAGMA table_info confirms that the column
-- is absent. SQLite does not support ADD COLUMN IF NOT EXISTS.
ALTER TABLE Soil ADD COLUMN Ssks REAL;
ALTER TABLE SoilLayers ADD COLUMN Ssks REAL;
