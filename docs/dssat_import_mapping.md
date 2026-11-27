# Importing a DSSAT experiment into MasterInput

A working map, written against one real experiment:
`dssat-csm-data/Maize/BRPI0202.MZX`, with its soil `BRPI020001` in
`Soil/BR.SOL` and its weather `Weather/BRPI0201.WTH`.

The aim is not to link to the DSSAT database. It is to find out **how much
of a real DSSAT simulation `MasterInput` can hold**, so that

```
model files ──run──▶ outputs A
      │
   import
      ▼
 MasterInput ──export + run──▶ outputs B      and A is compared with B
```

is a test with a meaning. Whatever has no home has to make the import fail
loudly, the way `NotApplicable` already does for what DSSAT cannot
simulate — never be dropped in silence, which is how the invented
irrigation survived.

`BRPI0202` is a good first case: 8 treatments, 4 cultivars × rainfed and
irrigated, 30 dated irrigations, 5 fertiliser applications, three soil
layers, two sets of initial conditions. Nothing exotic, and everything a
field experiment normally carries.

## The verdict, section by section

| DSSAT section | MasterInput | verdict |
|---|---|---|
| `*GENERAL` | nothing | **no home** — see below |
| `*TREATMENTS` | `SimUnitList`, `CropManagement` | **flattened**, see below |
| `*CULTIVARS` | `ListCultivars`, `ListCultOption` | holds it, partly invented |
| `*FIELDS` | `Coordinates`, `Soil` | holds it, a field becomes a pair |
| `*SOIL ANALYSIS` | nothing | **no home**, and inert here |
| `*INITIAL CONDITIONS` | `InitialConditions`, `InitialConditionsLayers` | partial |
| `*PLANTING DETAILS` | `CropManagement` | partial |
| `*IRRIGATION` | `IrrigationPolicy`, `IrrigationFOperations` | partial |
| `*FERTILIZERS` | `InorganicFertilizationPolicy`, `InorganicFOperations` | partial |
| `*RESIDUES` | `OrganicFertilizationPolicy`, `OrganicFOperations`, `ListResidues` | partial |
| `*SIMULATION CONTROLS` | `SimulationOptions` plus overrides | **mostly elsewhere** |
| soil file | `Soil`, `SoilLayers`, `RunoffTypes` | holds it |
| weather file | `Coordinates`, `RAclimateD` | holds it |

## `*GENERAL` — a new table

```
@PEOPLE   Cecilia M. Tojo Soler, Paulo C. Sentelhas, and Gerrit Hoogenboom
@ADDRESS  ESALQ - University of Sao Paulo
@SITE     Piracicaba, SP. Brazil
@ PAREA PRNO PLEN PLDR PLSP PLAY HAREA HRNO HLEN HARM
@NOTES    four publications, with their DOIs
```

None of it enters the simulation, and all of it is what makes the
simulation citable. The export invents a title from the ModelsDictionary, so
the round trip loses the provenance of the experiment.

A `GeneralInformation` table would hold it. One design point decides whether
it works: **the key must be the experiment, not the database.** A
`MasterInput` holds many simulations and will hold several imported
experiments, each with its own people, site and publications. One row per
database would silently keep the first import's provenance and attribute
every later simulation to it.

```
GeneralInformation(
    idProject  TEXT PRIMARY KEY,   -- "BRPI0202", the experiment code
    Title      TEXT,               -- *EXP.DETAILS
    People     TEXT,
    Address    TEXT,
    Site       TEXT,
    Notes      TEXT,               -- free text, publications and DOIs
    PlotArea REAL, PlotRows REAL, PlotLength REAL, ...  -- the PAREA line
)
```

with `SimUnitList.idProject` referencing it. The plot geometry (`PAREA` to
`HARM`) is `-99` here and in most experiments, but it is measurement
metadata rather than free text, so it deserves columns rather than the
`Notes` field.

## `*TREATMENTS` — the structure that does not survive

```
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 0 0 AG9010 - Rainfed           1  1  0  1  1  0  1  0  0  0  0  0  1
 5 1 0 0 AG9010 - IRRIGATED         1  2  0  2  1  1  2  0  0  0  0  0  1
```

A DSSAT treatment is a **vector of pointers** into the other sections, and
the eight treatments here are a factorial design: 4 cultivars × 2 water
regimes. Each column maps:

| column | points at | MasterInput |
|---|---|---|
| `CU` | `*CULTIVARS` | `CropManagement.Idcultivar` |
| `FL` | `*FIELDS` | `SimUnitList.idPoint` **and** `idsoil` |
| `IC` | `*INITIAL CONDITIONS` | `SimUnitList.idIni` |
| `MP` | `*PLANTING DETAILS` | `CropManagement.sowingdate`, `sdens` |
| `MI` | `*IRRIGATION` | `CropManagement.IrrigationPolicyCode` |
| `MF` | `*FERTILIZERS` | `CropManagement.InoFertiPolicyCode` |
| `MR` | `*RESIDUES` | `CropManagement.OFertiPolicyCode` |
| `MT` | `*TILLAGE` | `CropManagement.SoilTillPolicyCode` |
| `SM` | `*SIMULATION CONTROLS` | `SimUnitList.idOption`, partly |
| `SA` | `*SOIL ANALYSIS` | **nothing** |
| `MC` | chemical applications | **nothing** |
| `ME` | environmental changes | **nothing** |
| `MH` | `*HARVEST` | `CropManagement.DHarvest`, partly |

So eight treatments become **eight `SimUnitList` rows**, each with its own
`idMangt`, and the managements differ only by cultivar and irrigation
policy. `MasterInput` has no notion of a factor level, so the design is
flattened: the import can produce the right simulations but the export can
never rebuild one eight-treatment file from them.

**That is acceptable, and it is what makes the comparison honest.** The
round trip will write eight single-treatment X-files where DSSAT had one,
and the outputs must still match treatment by treatment. Comparing the
input files would fail for a reason that is not a defect; comparing the
`Summary.OUT` variables is the right target.

What the import must refuse: a non-zero `SA`, `MC` or `ME` level, because
those carry data with nowhere to go.

## `*CULTIVARS` — held, and half invented

```
@C CR INGENO CNAME
 1 MZ IB0171 AG9010
```

`CR` → `ListCultOption.CG`, `INGENO` → `ListCultivars.IdcultivarDssat`,
`CNAME` → `ListCultivars.CodCultivar`. The model code for `DSCROP` comes
from the genotype file the experiment uses (`MZCER048` → `CER047`/`CER048`,
the suffix being derived from the requested version).

The import must **invent** what no DSSAT file carries:
`ListCultivars.CodePSpecies` and `SpeciesName` (a key and a name of our
own), `ListCultOption.FicPlt` (the STICS plant file) and
`IdcultivarCelsius`. `MasterInput` is a multi-model database; a DSSAT import
fills the DSSAT columns and leaves the others empty, which means an imported
experiment **cannot be run under STICS** until someone supplies the plant
file. The import should say so rather than leave a hole that fails later.

## `*FIELDS` — a field is a pair

```
@L ID_FIELD WSTA....  FLSA FLOB  FLDT FLDD FLDS FLST SLTX SLDP ID_SOIL
 1 BRPI0001 BRPI0201   -99    0 DR000    0    0 00000 -99   120 BRPI020001
 2 BRPI0002 BRPI0201   -99    0 DR000    0    0 00000 -99   120 BRPI020002
```

Two fields, one weather station, two soils — the rainfed and irrigated
plots. DSSAT couples the weather and the soil in a field; `MasterInput`
splits them into `SimUnitList.idPoint` (the weather and coordinates) and
`idsoil`. So `FL` maps to the **pair**, and `ID_FIELD` itself has no home —
one more reason for a `GeneralInformation`-style place to keep the
experiment's own identifiers.

`WSTA` → `Coordinates.idPoint`, with `XCRD`/`YCRD`/`ELEV` into
`longitudeDD`/`latitudeDD`/`altitude` — all zero here, so they must come
from the weather file's header instead, which carries the real
`-22.430 / -47.250 / 580`. `SLDP` is the profile depth, already in
`Soil.SoilTotalDepth`. `FLDT`, `FLDD`, `FLDS`, `FLST`, `SLTX` have no home,
and are `-99` or a default code here.

## `*SOIL ANALYSIS` — nothing, and nothing lost here

```
@A SADAT  SMHB  SMPX  SMKE  SANAME
 1 02072   -99   -99   -99  -99
@A  SABL  SADM  SAOC  SANI SAPHW SAPHB  SAPX  SAKE  SASC
 1    15   -99   -99   -99   -99   -99   -99   -99   -99
```

Every measurement is `-99`, and the treatments point at level `0`, so the
section is inert in this experiment — which is why it is a good first case.
The export writes an equally empty section, so the round trip is clean.

An experiment with real analysis values has nowhere to put them: `IPSLIN.for`
uses them to override the soil profile, so they change results and cannot be
ignored. Such an experiment must fail the import until the schema grows a
`SoilAnalysis` table.

## `*INITIAL CONDITIONS` — partial

```
@C   PCR ICDAT ICRT ICND ICRN ICRE ICWD ICRES ICREN ICREP ICRIP ICRID ICNAME
 1    MZ 02060  -99  -99    1    1  -99  5100   1.5   -99   100    15 rainfed
@C  ICBL  SH2O  SNH4  SNO3
 1    20   .25    .4   3.9
```

`InitialConditions` holds `WStockinit`, `Ninit`, `option`, `NH4initf`, and
`InitialConditionsLayers` the per-layer values, so `ICBL`/`SH2O`/`SNH4`/
`SNO3` have a home. Without one:

- `PCR`, the **previous crop** — matters for residue decomposition;
- `ICDAT`, the date the conditions were measured;
- `ICRES` 5100 kg/ha and `ICREN` 1.5 %, the residue mass and its nitrogen —
  these feed the organic matter balance and are not decoration;
- `ICRIP`, `ICRID`, the residue incorporation percentage and depth.

Two levels here, rainfed and irrigated, so two `idIni`.

## `*PLANTING DETAILS` — partial

```
@P PDATE EDATE PPOP PPOE PLME PLDS PLRS PLRD PLDP PLWT PAGE PENV PLPH SPRL
 1 02072 02078    7    5    S    R   80   45    5  -99  -99  -99  -99    0
```

`PDATE` → `CropManagement.sowingdate` (day of year), `PPOP` → `sdens`.
Without a home: `EDATE` (the observed emergence), `PLME` (transplant or
seed), `PLDS` (row or broadcast), `PLRS` **80 cm row spacing** — the
`interrang` of the STICS discussion, and a real agronomic input —, `PLRD`
(row direction), `PLDP` (5 cm sowing depth), `PPOE` (the population that
actually emerged, 5 against 7 sown).

`PLRS` and `PLDP` are the two that change results.

## `*IRRIGATION` — partial, and a conversion

```
@I  EFIR  IDEP  ITHR  IEPT  IOFF  IAME  IAMT IRNAME
 1    .9    30    50   100 GS000 IR001    10 -99
@I IDATE  IROP IRVAL
 1 02075 IR004     7     ... thirty applications
```

`IrrigationFOperations` holds `DIrrigation` and `IrrigationAmount`, so the
thirty applications fit — but `DIrrigation` is **relative to sowing** while
`IDATE` is absolute, so the import computes `IDATE − PDATE`: the first
application on day 075 against a sowing on day 072 gives `+3`, the last on
day 182 gives `+110`. A pre-sowing application would give a negative offset,
which is the normal case for a tillage or a manure spreading and which
`format_dssat_yyddd` now handles in both directions.

Without a home: `IROP`, the **method of each application** (`IR004`, sprinkler
here) — the schema has one method for the policy and none per operation —,
and the automatic-irrigation header `EFIR`, `IDEP`, `ITHR`, `IEPT`, which
only matter when `IRRIG` is `A`.

## `*FERTILIZERS` — partial

```
@F FDATE  FMCD  FACD  FDEP  FAMN  FAMP  FAMK  FAMC  FAMO  FOCD
 1 02072 FE027 AP001     5    20   -99   -99   -99   -99   -99
 1 02093 FE005 AP003     0    50     0     0     0     0   -99
```

`InorganicFOperations` holds `Dferti`, `N`, `P`, `K`, again as an offset from
sowing. Without a home: `FMCD`, the **material** (`FE027` urea, `FE005`
ammonium nitrate — different volatilisation), `FACD` the application method,
`FDEP` the depth. Two levels here: rainfed gets 20 then 50 kg N, irrigated 26
then 50 then 50.

## `*RESIDUES` — held

`RDATE`, `RCOD`, `RAMT`, `RESN` map to `OrganicFOperations` through
`ListResidues`, which is the route the fixture's `FERT_MIN_ORG` already
exercises. `RAMT` is 0 here, so the section is inert.

## `*SIMULATION CONTROLS` — mostly outside MasterInput

```
 1 GE  NYERS 1  NREPS 1  START S  SDATE 02060  SNAME 2002 Maize Experiment
 1 OP  WATER Y  NITRO Y  SYMBI N  PHOSP N  POTAS N  ...
 1 ME  WTHER M  INCON M  LIGHT E  EVAPO R  INFIL S  PHOTO R  ...
 1 MA  PLANT R  IRRIG R  FERTI R  RESID N  HARVS M
 1 OU  ... and the AUTOMATIC MANAGEMENT block
```

`SimulationOptions` holds exactly four flags — `StressW_YN`, `StressN_YN`,
`StressP_YN`, `StressK_YN` — which are `WATER`, `NITRO`, `PHOSP` and
`POTAS`. Everything else lives in `ModelsDictionary` as a model-wide default.

So importing this section means **writing override rows** into
`CropManagementParameterOverrides`, keyed by
`(idMangt, SeasonOrder, PlantOrder)` with `TargetTable =
dssat_x_simulation_method` and so on. That mechanism exists and is already
exercised by the fixture's `MEPHO` row; what is missing is that only
`dssat_x_simulation_method` is wired into `OVERRIDABLE_TABLES`. The import
needs `_option`, `_management`, `_outputs` and the automatic-management
tables added, which is one line each plus a `prefetch_management` call.

Two values with no route at all:

- `SDATE` 02060 and `NYERS` 1 → `SimUnitList.StartYear`/`StartDay` and
  `EndYear`/`EndDay`, so those are fine;
- `HARVS M`, harvest at maturity. `MasterInput` has `DHarvest`, a duration
  in days, and no way to say "when the crop matures". This is the same gap
  the fixture's rotation ran into. A sentinel value, or a column, is needed.

## The soil and weather files

Both map cleanly, which is the reassuring part.

```
*BRPI020001  ESALQ  C  120  TERRA ROXA (RAINFED)
@ SCOM SALB SLU1 SLDR SLRO SLNF SLPF SMHB SMPX SMKE
     R 0.14  6.0 0.30 83.0 1.00 0.90 IB00 IB00 IB00
@  SLB SLMH SLLL SDUL SSAT SRGF SSKS SBDM SLOC SLCL SLSI SLCF SLNI SLHW ...
    20    A 0.170 0.280 0.450 1.000 0.10 0.90 1.40 61.0 17.0  0.0 0.100 5.0
```

`SALB` → `Soil.albedo`, `SLRO` 83 → `RunoffTypes.CurveNumber`, the layer
lines → `SoilLayers` (`SLB`→`Ldown`, `SLLL`→`Wwp`, `SDUL`→`Wfc`,
`SSAT`→`Ssat`, `SSKS`→`Ssks`, `SBDM`→`bd`, `SLOC`→`OrganicC`,
`SLCL`→`Clay`, `SLSI`→`Silt`, `SLCF`→`cf`, `SLNI`→`TotalN`, `SLHW`→`pH`).
This is a `detailed` soil, three layers — so an imported experiment would
finally exercise the layer path that nothing covers today.

Note the unit work: `SLLL`/`SDUL`/`SSAT` are volumetric fractions for the
whole soil while `MasterInput` stores fine-earth percentages, and the DSSAT
converter already does that correction in the other direction
(`_number(wwp) / 100 * fine_earth`). The import has to undo it, and getting
it wrong is invisible in the files and visible in the yields.

`SLU1`, `SLDR`, `SLNF`, `SLPF`, `SCOM`, `SLMH`, `SRGF`, `SCEC` have no home.
`SRGF`, the root growth factor by layer, is the one that changes results.

The weather file maps to `Coordinates` and `RAclimateD`:

```
@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT
  BRPI  -22.430  -47.250   580  21.6   7.2 -99.0   2.0
@DATE  SRAD  TMAX  TMIN  RAIN
```

`TAV` and `AMP` have columns, added by the `20261023` migration. `REFHT`
and `WNDHT` have none — and `WNDHT` is the measurement height that STICS
calls `zr`, the parameter whose value we had to raise by hand for the
fixture. An import would supply it from the data instead of a default.

## Where the missing fields go: the override tables

`MasterInput` does not need a column per model parameter, and it should not
get one. It already carries three generic override tables; two more places
are needed, for the initial conditions and for a single operation:

| table | key | what it qualifies |
|---|---|---|
| `SoilParameterOverrides` | `IdSoil, Model, TargetTable, Parameter, NumLayer` | a soil, whole profile (`NumLayer = 0`) or one layer (`1..n`) |
| `CropManagementParameterOverrides` | `idMangt, SeasonOrder, PlantOrder, Model, TargetTable, Parameter` | one crop-season of one management |
| `PointParameterOverrides` | `idPoint, Model, TargetTable, Parameter` | a point, so a weather station |
| an extension of `InitialConditions` | `idIni` | one set of initial conditions |
| `OperationParameterOverrides` | `idOperation, Model, TargetTable, Parameter` | one irrigation, fertiliser, residue or tillage operation |

**The rule that makes this work: store a value only when it differs from the
`ModelsDictionary` default.** The override tables then hold the *delta*
between this experiment and the model's own defaults — which keeps an import
small, makes it reviewable as a diff, and keeps `MasterInput` model-neutral.
A parameter absent from the overrides means "whatever the model usually
does", which is what a dictionary default already means.

So the gap list from the sections above is not a schema problem. It is a
routing problem:

| field | DSSAT section | goes to | `TargetTable` | key |
|---|---|---|---|---|
| `PLRS`, `PLDP`, `PLME`, `PLDS`, `PPOE`, `EDATE` | planting | `CropManagementParameterOverrides` | `dssat_x_planting_details` | crop-season |
| `HARVS`, and all of `OPTIONS`, `METHODS`, `MANAGEMENT`, `OUTPUTS`, `AUTOMATIC MANAGEMENT` | simulation controls | `CropManagementParameterOverrides` | `dssat_x_simulation_*` | crop-season |
| `SRGF`, `SLMH` | soil, per layer | `SoilParameterOverrides` | the layer table | `NumLayer = 1..n` |
| `SLDR`, `SLU1`, `SLNF`, `SLPF`, `SCOM` | soil, whole profile | `SoilParameterOverrides` | the site table | `NumLayer = 0` |
| `SADM`, `SAOC`, `SANI`, `SAPHW`, `SAPX`, `SAKE` | soil analysis | `SoilParameterOverrides` | `dssat_x_soil_analysis_data` | `NumLayer = 1..n` |
| `WNDHT`, `REFHT` | weather header | `PointParameterOverrides` | `dssat_weather_site` | point |
| `PCR`, `ICDAT`, `ICRES`, `ICREN`, `ICRIP`, `ICRID` | initial conditions | extension of `InitialConditions` | — | `idIni` |
| `IROP` | irrigation, per application | `OperationParameterOverrides` | `dssat_x_irrigation_water_data` | `idIrrigation` |
| `FMCD`, `FACD`, `FDEP` | fertilisers, per application | `OperationParameterOverrides` | `dssat_x_fertilizer` | `idFertInorg` |

Two of these deserve a note.

**`*SOIL ANALYSIS` stops being a gap.** Its values are per layer, which is
exactly what `SoilParameterOverrides.NumLayer` is for: `0` for the whole
profile, `1..n` for a layer. An experiment carrying real analysis values
becomes importable without a new table.

**`WNDHT` is STICS's `zr`.** It is the weather measurement height, the
parameter whose value had to be raised by hand in the fixture because the
dictionary default of 2.0 m was below the maize canopy. Imported from the
weather file into `PointParameterOverrides`, it would come from the data
instead of a default — and both models would read the same number, which is
the point of the database.

### Per-operation values: a fifth override table

A value belonging to **one operation** -- `IROP`, the method of each of the
thirty irrigations, or `FMCD`, `FACD` and `FDEP`, the material, method and
depth of each of the five fertiliser applications -- is reached the same
way, because an operation has an identity:

| table | own key | natural key |
|---|---|---|
| `IrrigationFOperations` | `idIrrigation` | `(IrrigationPolicyCode, IrrigationNumber)` |
| `InorganicFOperations` | `idFertInorg` | `(InorgFertiPolicyCode, IFNumber)` |
| `OrganicFOperations` | `idFertOrga` | `(OFertiPolicyCode, OFNumber)` |
| `SoilTillageOperations` | `IdTillOp` | `(SoilTillPolicyCode, STNumber)` |

The strategy is named from `CropManagement` -- `IrrigationPolicyCode` and
its siblings -- and an operation is that strategy plus its number. So a
fifth table follows the shape of the other four:

```
OperationParameterOverrides(
    idOperation TEXT NOT NULL,   -- idIrrigation, idFertInorg, idFertOrga, IdTillOp
    Model       TEXT NOT NULL,
    TargetTable TEXT NOT NULL,   -- which also says the family: _irrigation_water_data,
    Parameter   TEXT NOT NULL,   -- _fertilizer, _residues, _tillage
    Value       TEXT NOT NULL,
    PRIMARY KEY (idOperation, Model, TargetTable, Parameter)
)
```

`FE027` for the first application and `FE005` for the second is two rows,
and the thirty `IR004` are thirty rows -- or none, when they equal the
dictionary default, which is the usual case and why the delta rule keeps
this small.

**A column on the operation table would be the wrong answer**, and it was
this document's first recommendation. `FMCD` is a DSSAT material code;
putting it in `InorganicFOperations` would place a model-specific value in a
model-neutral table, which is what the override mechanism exists to avoid.
The operation tables keep what every model needs -- when, how much, of which
nutrient -- and the override tables keep what one model asks in addition.

### What this asks of the export

The import is the easy half. For an override to have any effect, **the
writer that emits the value must read it through the resolver** instead of
taking the dictionary default. The soil level is broadly wired already --
`resolve` and `resolve_layers` are used by STICS v11 `paramsol`, DSSAT's
soil and X writers, APSIM's soil writer and CELSIUS. What is not:

- the **point** level is honoured by STICS v11's station writer and by
  nothing else, so a `PointParameterOverrides` row does not reach a DSSAT or
  APSIM weather file -- which is exactly where `WNDHT` lands;
- the **crop-season** level is honoured by STICS v11 `fictec1` and, in
  DSSAT, by `dssat_x_simulation_method` alone, through `OVERRIDABLE_TABLES`
  in `dssatxconverter.py`, which the `MEPHO` work added. Every other DSSAT
  writer takes `DT[DT["Champ"] == name]["dv"].values[0]` directly;
- the **operation** level has nothing to honour yet.

Routing a writer through `ParameterResolver` is uniform: it already offers
`resolve()` and `resolve_layers()` for
a soil, `resolve_management()` for a crop-season and `resolve_point()` for a
point, and the prefetch must happen in the parent process because a worker
sees only the defaults.

That is also what makes the round trip meaningful. An import that writes
overrides the export ignores would compare as a difference, and the
difference would be ours.

## The order of work

1. **Wire the export to the overrides**, table by table, starting with the
   ones `BRPI0202` needs: planting details, the simulation controls that are
   not yet covered, the soil site and layer tables, and the weather site.
   Each is a `TargetTable` added to the overridable set plus a prefetch in
   the parent.
2. **Extend `InitialConditions`** for the previous crop, the measurement
   date and the initial residues.
3. **Add `OperationParameterOverrides`**, keyed by the operation's own
   identity, for the per-application values.
4. **Write the import** for one experiment, storing only what differs from
   the dictionary defaults.
5. **Compare the two runs' output variables**, not their input files.

`BRPI0202` stays the right first experiment: its soil analysis is empty and
its residues are zero, so two gaps do not bite, while its three-layer
detailed soil and its thirty irrigations are exactly the paths with no
coverage today.


## DSSAT to ICASA variable correspondence

The `comments` column contains `to be converted` when the listed DSSAT and
ICASA units differ. This comparison is separate from conversion to MasterInput
units and measurement bases. ICASA dates denote a date type, not a physical unit.

| DSSAT variable | ICASA code | DSSAT unit/type | ICASA unit/type | comments |
|---|---|---|---|---|
| ID_FIELD | FIELD_ID | text | text | |
| ID_SOIL | SOIL_ID | text | text | |
| PDATE | PDATE | date | date | |
| PPOP | PLPOP | plants/m² | plants/m² | |
| PPOE | PLPOE | plants/m² | plants/m² | |
| PLRS | PLRS | cm | cm | |
| PLDP | PLDP | cm | mm | to be converted |
| IDATE | IDATE | date | date | |
| IROP | IROP | code | code | |
| IRVAL | IRVAL | mm | mm | |
| FDATE | FEDATE | date | date | |
| FMCD | FECD | code | code | |
| FACD | FEACD | code | code | |
| FDEP | FEDEP | cm | cm | |
| FAMN | FEAMN | kg N/ha | kg N/ha | |
| FAMP | FEAMP | kg P/ha | kg P/ha | |
| FAMK | FEAMK | kg K/ha | kg K/ha | |
| RAMT | OMAMT | kg dry matter/ha | kg dry matter/ha | |
| SLB | SLLB | cm | cm | |
| SLLL | SLLL | cm³/cm³ | cm³/cm³ | |
| SDUL | SLDUL | cm³/cm³ | cm³/cm³ | |
| SSAT | SLSAT | cm³/cm³ | cm³/cm³ | |
| SSKS | SKSAT | cm/h | cm/h | |
| SBDM | SLBDM | g/cm³ | g/cm³ | |
| SLOC | SLOC | % | % | |
| SLCL | SLCLY | % | % | |
| SLSI | SLSIL | % | % | |
| SRGF | SLRGF | unitless | unitless | |
| SRAD | SRAD | MJ/m²/day | MJ/m²/day | |
| TMAX | TMAX | °C | °C | |
| TMIN | TMIN | °C | °C | |
| RAIN | RAIN | mm/day record | mm/day record | |
| TAV | TAV | °C | °C | |
| AMP | TAMP | °C | °C | |
| WNDHT | WNDHT | m | m | |
| REFHT | REFHT | m | m | |

Sources: official ICASA dictionary sections
[Management](https://github.com/DSSAT/ICASA-Dictionary/blob/main/CSV/Management_info.csv),
[Soils](https://github.com/DSSAT/ICASA-Dictionary/blob/main/CSV/Soils_data.csv), and
[Weather](https://github.com/DSSAT/ICASA-Dictionary/blob/main/CSV/Weather_data.csv).
