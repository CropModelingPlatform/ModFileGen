-- Add layer-specific saturated water content for DSSAT.
--
-- Unit: percent volumetric water content, consistent with SoilLayers.Wfc and
-- SoilLayers.Wwp. NULL falls back to Soil.Ssat, then Wfc * 1.01.
-- Apply only when PRAGMA table_info(SoilLayers) confirms the column is absent.
ALTER TABLE SoilLayers ADD COLUMN Ssat REAL;
