-- Optional site temperature parameters for DSSAT weather files.
--
-- Coordinates.tav: annual average ambient temperature (degC).
-- Coordinates.amp: annual amplitude of mean monthly temperature (degC).
--
-- When a value is NULL (or the column is absent), the DSSAT weather converters
-- use the ModelsDictionary default (Variables, model 'dssat',
-- table 'dssat_weather_site').
--
-- Apply each statement only when PRAGMA table_info(Coordinates) confirms that
-- the column is absent. SQLite does not support ADD COLUMN IF NOT EXISTS.
ALTER TABLE Coordinates ADD COLUMN tav REAL;
ALTER TABLE Coordinates ADD COLUMN amp REAL;
