-- Layer-wise soil parameter overrides.
--
-- SoilParameterOverrides.NumLayer:
--   0      the whole profile (every override created before this migration);
--   1..n   one layer, numbered as in SoilLayers (a 'simple' soil has layer 1).
--
-- For a layer parameter at layer k, ParameterResolver.resolve_layers() uses the
-- layer k override, else the profile (0) override, else the ModelsDictionary
-- default. Whole-soil parameters (for example q0) accept NumLayer = 0 only.
--
-- NumLayer joins the primary key, which SQLite cannot alter: the table is
-- rebuilt in rowid order. Apply only when PRAGMA table_info(SoilParameterOverrides)
-- has no NumLayer column. Databases without NumLayer keep working: all their
-- overrides are read as whole-profile values.

CREATE TABLE SoilParameterOverrides_new (
    IdSoil      TEXT NOT NULL,
    Model       TEXT NOT NULL,
    TargetTable TEXT NOT NULL,
    Parameter   TEXT NOT NULL,
    Value       TEXT NOT NULL,
    NumLayer    INTEGER NOT NULL DEFAULT 0 CHECK (NumLayer >= 0),
    PRIMARY KEY (IdSoil, Model, TargetTable, Parameter, NumLayer),
    FOREIGN KEY (IdSoil) REFERENCES Soil (IdSoil)
);

INSERT INTO SoilParameterOverrides_new (IdSoil, Model, TargetTable, Parameter, Value)
SELECT IdSoil, Model, TargetTable, Parameter, Value
FROM SoilParameterOverrides
ORDER BY rowid;

DROP TABLE SoilParameterOverrides;
ALTER TABLE SoilParameterOverrides_new RENAME TO SoilParameterOverrides;

CREATE INDEX IF NOT EXISTS idx_soil_parameter_override_lookup
ON SoilParameterOverrides (Model, TargetTable, IdSoil);
