# ModFileGen TODO

This file is the project's persistent task list. Keep tasks short, actionable,
and linked to an issue or pull request when one exists.

## In progress

- [ ] Complete soil-specific parameter support for DSSAT using
  `ParameterResolver` and `SoilDataRepository`.
- [ ] Verify the STICS v11 `q0` computed strategy in standard and successive
  notebook runs, including multi-worker runs.

## Next

- [ ] Make ModFileGen usable on Windows and macOS without WSL, so students
  without admin rights can run it (branch `cross-platform`):
  1. **done in `71102ffd`**: `engine_runner.py` plus one `*runner.py` per
     model replace the seven `.sh` scripts and the five
     `subprocess.run(["bash", ...])` call sites; `codeseprapport` is
     generated as 2 instead of patched by `sed -i -z`. Equivalence checked on
     the real engines (identical summary CSVs; only the engines' own
     timestamped raw outputs differ) and the launcher overhead dropped from
     14.65 ms to 1.04 ms per simulation. `run_engine` falls back to the
     platform interpreter for a wrapper the OS will not exec, such as DSSAT's
     shebang-less `run_dssat`;
  2. **done in `98ac2433`**: `modfilegen.engines` resolves all seven
     executables through one cascade (`GlobalVariables` key, environment
     variable, PATH, known install locations, bare name), with `.exe`
     handling and a first look under `~/.modfilegen/engines/<engine>` for a
     portable no-administrator install. STICS is never taken from PATH,
     because v9 and v11 share the `stics_modulo` name. APSIM keeps its
     `apsim_path = None` generate-only mode. Failures now name the key and
     the environment variable to set;
  3. **done in `59426136`**: `modfilegen.text_files` states one policy and
     the 44 `open()` call sites use it. Writes are UTF-8 with LF on every
     platform; engine output is decoded leniently, since DSSAT and STICS emit
     bytes strict UTF-8 rejects (0xF8, 0xB0) and crashing on those loses a
     simulation. `pandas.read_csv` needed nothing: it defaults to UTF-8, not
     the locale. Cultivar and plant files keep their CRLF convention, which
     `ficplt1.txt` proves the engines accept;
  4. guard against the Windows `MAX_PATH` limit on USM directories and against
     file locks when `dt=1` deletes them. `agriscale run --temp` already lets
     a caller shorten the path by hand, and `--delete-intermediate` is the
     switch that exercises the lock case;
  5. add `windows-latest` and `macos-latest` to the CI matrix. `agriscale
     selftest` is what it should run: it needs no engine and already covers
     the encoding, path and date handling that differed. A generation-only
     mode would let it check the generated files too.
  6. **done in `7913d9de`, `078a482c`, `999330cf` and this commit**: verify
     rather than download. `agriscale engines` reports where each engine was
     found and tells `not found` (ModFileGen cannot see it) from
     `incomplete` (the executable was copied away from the files it needs
     beside it), naming the key and the variable to set in the syntax of the
     reader's own shell -- every shell is listed, since Git Bash and WSL run
     sh on Windows and `os.name` cannot tell. `docs/source/engines.rst`
     covers where each engine comes from and what to unpack, with
     `tests/test_engines_documentation.py` guarding it against drift. An
     `install_engines` downloader was dropped: all three public models are
     behind a free registration (INRAE forge account, a DSSAT e-mail form,
     an APSIM licence choice), so none can be fetched unattended.
     `JavaSTICS-v11.0.0-rc2.zip` carries both `bin/stics_modulo` and
     `bin/stics_modulo.exe`, so STICS needs no build step on either
     platform.
  Engine availability, as the official pages state it: only STICS is
  confirmed to ship a Windows simulator in its archive. DSSAT and APSIM
  advertise Windows and macOS support but neither page says what the package
  format is, so "official Windows build" is a claim their own documentation
  does not make. CELSIUS v3 and `datamill` turned out to be `net5.0`
  applications rather than native binaries, so like CELSIUS V32 they need
  `dotnet publish --runtime win-x64`, ideally `--self-contained` to avoid
  asking a student for a .NET install.
- [x] `agriscale run` generates the input files and starts one model, with an
  exit status: 0 ran, 1 failed, 2 misconfigured. It fills `GlobalVariables`
  and calls the dispatcher the notebooks call, so nothing runs per simulation
  and the parallel path is untouched. The engine is resolved before any file
  is generated, intermediate files are kept by default (the opposite of the
  library default, since on a first run they are the only evidence of what
  the engine was given), and `--manifest` writes a sha256 listing with
  forward slashes so a Windows run compares with a Linux one byte for byte.
  Documented in `docs/source/command_line.rst`, guarded by a test that the
  page names every option the parser accepts -- which immediately caught
  four it did not.
- [x] The committed CSV fixture now runs end to end under STICS v11
  successive: 5 simulations, a 3-season rotation, 10 `SummaryOutput` rows,
  exit 0. Two defects were in the way. `sticsv11.station.zr` was 2.0 m while
  every maize plant file has `hautmax` 2.5 m, and STICS exits 9 when the
  weather measurement height is not above the crop under Shuttleworth-Wallace
  (`codeetp` 3); raised to 3.0 m, documented in `tests/fixtures/README.md`.
  And `sticsfictec1converter` asked the v11 dictionary for the v9 field name
  `supply of organic residus.eaures`, which only exists as `eaures` under
  `sticsv11`/`fictec1`, so any management supplying organic residues died in
  `FormatSticsRawData` with a bare numpy IndexError. It now raises a KeyError
  naming the parameter and the table.
- [x] The fixture also runs under DSSAT v4.8: exit 0, 2 `SummaryOutput` rows
  for the two single-crop simulations, and the three association simulations
  refused by name. Three defects were in the way. `ListCultivars
  .IdcultivarDssat` was NULL for both test cultivars, so every DSSAT run died
  formatting `INGENO`; the cultivar converter copies the genotype files
  without adding a line, so the code has to exist in the `.CUL` already.
  `ListCultOption.DSCROP` was empty for the peanut. And standard DSSAT had no
  association check at all, unlike the successive converter: it took whichever
  plant row came back first and wrote a single-crop simulation from an
  intercrop, dropping a crop with no message.
- [ ] `writeBlockResidues` was asking numpy for the truth of a whole column
  (`if dataTable["idresidueDssat"].values:`), which works with one residue
  row and raises with two, so no management applying organic matter twice
  could be converted. Fixed to test the row being written. Worth sweeping the
  DSSAT converters for the same shape: this one was the only `.values :`
  spelling, but `.values[0]` on a multi-row frame is the same class of bug and
  standard mode reads every season of a rotation management.
- [x] `agriscale run` reconciles what was asked with what ran.
  `modfilegen.Converter.DssatConverter.applicability` answers, without
  running anything, how many crop-seasons a database asks for and how many
  DSSAT can take on; the command prints that before starting and fails when
  fewer are produced than were applicable. A `SimUnitList` row is not a
  simulation -- five rows ask for ten crop-seasons on the fixture -- which is
  how a truncated rotation passed unnoticed. `NotApplicable` is the
  distinction: declined work is not a defect, and still exits 0.
- [ ] Standard DSSAT now refuses a rotation instead of simulating season 1
  and dropping the rest, and successive DSSAT skips an association instead of
  killing the whole `Parallel` call on the first one. Give STICS the same
  survey hook, so its runs are reconciled too: it declines nothing today, but
  the count would have caught the `eaures` defect.
- [x] A crop-season can carry its own simulation controls. DSSAT numbers a
  whole `SIMULATION CONTROLS` block at once and a treatment's `SM` column
  points at it, so two crop-seasons needing one different value need two
  blocks -- as DSSAT's own `UFGA7803.SQX` does, four treatments over two
  blocks with `PHOTO` `L` and `C`. The writer emitted the first rotation's
  block only and hard-coded `SM` to 1. It now groups the rotations by the
  controls they will actually be written with and numbers one block per
  distinct set, so identical controls still produce exactly one block and
  the generated file is byte-identical to before. No schema change: the
  existing `CropManagementParameterOverrides`, keyed by
  `(idMangt, SeasonOrder, PlantOrder)`, is already per crop-season, and any
  field of `dssat_x_simulation_method` can be overridden -- which one is the
  user's decision. Verified: an override of `MEPHO` on season 2 yields two
  blocks with `PHOTO R` and `PHOTO L` and `SM` = 1, 2, 1.
- [x] `@  AUTOMATIC MANAGEMENT` is written for every `SIMULATION CONTROLS`
  level, whatever the `MANAGEMENT` switches say. It was gated on a switch
  being `A`, and the fixture's are `R` and `M`, so no level ever had it; with
  one level DSSAT tolerates that, with several it fails reading the file
  (error 5010, key `IPSIM`). Writing it always exposed a defect it had been
  hiding: `PWDINF` and `PWDINL` hold 5161 and 5175, `yyddd` dates from a
  template whose year was 05, and the code prefixed them with the
  simulation's year as if they were days -- `005161`, six digits in a
  six-wide field, so the two dates ran together. Only the day is kept now,
  and the line matches the official example column for column.
- [x] The fixture carries one parameter override per model, so the generic
  per-crop-season route is exercised by default rather than by hand:
  `sticsv11.fictec1.codecalirrig` on season 3 and
  `dssat.dssat_x_simulation_method.MEPHO` = `L` on season 2, the peanut.
- [x] A `SIMULATION CONTROLS` block is duplicated only when a control
  element really differs between treatments. The AUTOMATIC MANAGEMENT
  section is written on every level because DSSAT's reader needs the
  structure, and each rotation generated its windows from its own dates, so
  two seasons growing the same crop under identical controls differed on
  `PL` and `HA` alone and took a block each. Those windows are now made
  sequence-wide *while their switch leaves them unused* -- `PLANT` other
  than `A` for the planting window, `HARVS` other than `A` for the harvest
  one. Turn a switch to `A` and the window becomes a real instruction, its
  per-season values stand, and the blocks differ again. On the fixture:
  2 blocks, `SM` = 1, 2, 1, the maize seasons sharing the first and the
  peanut taking the second for its `MEPHO`, exactly the shape of
  `UFGA7803.SQX`.
- [x] The season boundary rule is confirmed and documented: a season ends the
  day before the **next season's first cultural operation**, not the day
  before its sowing. Both converters already implemented it, in the same
  shape (`dssatsuccessiveconverter.py:571`,
  `sticssuccessiveconverter.py:258`), and each had a test of its own; what
  nothing pinned was that the two agree.
  `tests/test_successive_season_boundaries.py` now holds both models to the
  rule and to each other, and `docs/source/database.rst` states it with the
  fixture's eleven-day gap worked through -- season 2 irrigates ten days
  before sowing, so season 1 closes eleven days before it, which is
  invisible unless someone goes looking.
- [x] DSSAT writes the irrigations the database declares. The block was
  written from the ModelsDictionary alone -- one line carrying `IDLAPL`,
  `IRRCOD` and `IIRV`, which are template defaults -- so the fixture's three
  irrigations of 20, 30 and 30 mm came out as a single 27.9 mm on `10177`, a
  date in no year of the simulation, and nothing said so. It now reads
  `IrrigationFOperations` as the fertiliser block already did, honours
  `IIRRI = D` for days after planting, and keeps the dictionary line when no
  database is passed. `format_dssat_yyddd` also gained the missing direction:
  it rolled a day past December into the next year but not a day below 1 into
  the previous one, so a crop sown early in the year with a pre-sowing
  operation produced a day of 0 or less.
- [ ] Audit the other X-file blocks for the same shape. The irrigation one
  took every value from the dictionary; the fertiliser and residue ones read
  the database. Each remaining block should be checked for which of the two
  it is, since a block written from defaults looks entirely plausible in the
  file.
- [x] The rotation runs under DSSAT v4.8: exit 0, no `ERROR.OUT`, four
  crop-seasons produced against four applicable. `DEMAND` was the harvest
  date, not `MEPHO`: the season window was written as `HDATE`, so the peanut
  stood for 364 days and CROPGRO hit its limit of 300 flower cohorts.
  `DHarvest` now caps it -- the window end while it is shorter, sowing plus
  `DHarvest` when the window is longer. The windows themselves do not move,
  and DSSAT needs no continuity there since it starts the next run the day
  after this one ends and simulates bare soil until that season's own sowing.
- [ ] `NYERS` cannot bound a sequence at a season count. `CSM.for` uses it
  once, at the first run, for `YRDOY_END = (year + NYERS) * 1000 + day - 1`,
  then sets it to 1; the sequence ends only when that date is reached, and
  the treatment list is cycled until then. The span is a whole number of
  years from the start day, so slack after the last declared harvest cannot
  be removed: 133 days on the fixture's rotation, and no integer `NYERS`
  helps. The summary reader therefore drops a cycle sown past the
  simulation's own end, which is what separates an engine repeat from a
  one-season management legitimately repeating over the period. Worth
  revisiting if DSSAT ever gains a sequence end date.
- [ ] DSSAT leaves `chunk_0.csv` in the output directory rather than in the
  scratch directory; it is an intermediate, and it shows up in the manifest.
- [ ] Decide whether the summary CSV should keep its `uuid4` prefix. It
  prevents collisions between parallel and repeated runs, but makes the file
  name differ between two runs of the same inputs; `agriscale run --manifest`
  works around it by substituting `<run-id>`. A name derived from the run's
  inputs would serve both ends.
- [x] The fixture ships inside the package, so `pip install modfilegen` is
  self-sufficient: the CSV sources, the STICS plant files and the DSSAT 048
  genotypes moved from `tests/fixtures/sources` to
  `src/modfilegen/data_fixtures`, 1.1 MB of text, and the builder moved to
  `modfilegen.fixtures` with a shim left at the old path so the tests and
  the documented command line keep working. `agriscale fixture` writes the
  demo databases and prints the run command with the paths filled in.
  Verified from a clean venv outside the repository, from both the wheel and
  the source archive: the STICS v11 successive run produces a manifest
  identical to the repository's.
- [x] `agriscale selftest` checks an installation with no engine, which is
  what a student has just after installing: it builds the packaged fixture
  and compares its rows against a digest shipped beside them, then checks
  one thing per cross-platform defect (UTF-8 with LF, path splitting, APSIM
  month names, DSSAT year boundaries) and reports which engines are visible.
  A missing engine is not a failure.
- [x] A user's plant and genotype files reach the engine untouched, and a
  test holds the three converters to it. They come from the user in whatever
  shape -- CRLF, LF, mixed, cp1252, a byte-order mark, no final newline --
  and all three copy them byte for byte with `shutil.copyfile`, never
  decoding them. A source guard refuses an `open()` on these paths, because
  routing them through `modfilegen.text_files` would look like an
  improvement and would normalise the line endings and raise on anything
  that is not UTF-8.
- [ ] `agriscale selftest` cannot generate a model's input files: the
  converters write a simulation's files and start the engine in the same
  loop, so there is no generation-only path. Adding one would let the
  self-test and CI check the generated files themselves, which is the
  strongest check available without an engine, and it is what step 5's
  "generation-only tests" assumed existed.
- [ ] Publish to PyPI. Both artefacts build and pass `twine check`; the names
  `modfilegen` and `agriscale` are free. The upload needs an account and an
  API token, which are the maintainer's to hold.
- [ ] CELSIUS V32 soils only call `ParameterResolver.resolve()`, so a layer
  override (`NumLayer` > 0) on its `Soil` table is silently ignored; reject it
  with `resolve_layers("celsius", "Soil", soil_id, layer_count, ())`.
- [ ] DSSAT successive builds its soil services once per group (one simulation);
  share them across the groups of a worker batch, as STICS v11 successive does.
- [ ] Design and implement a generic strong-coupling framework for crop models:
  define language-neutral state/action schemas and engine/policy adapters, then
  validate the first daily closed-loop coupling with the STICS JSON-RPC server
  (`init_simulation`, `get_variable`, `add_irrigation`, `execute_day`) and an
  external irrigation decision model such as Optirrig/R. Keep STICS as the
  biophysical state authority, support persistent processes and batched
  simulations, and provide fallback adapters for models without a daily-step
  API.
- [ ] Integrate the common output configuration service into each converter and replace per-model hard-coded `SummaryOutput` mappings.
- [ ] Extend dynamic DSSAT synthesis import from `Summary.OUT` to aggregated `PlantGro.OUT`, `SoilNi.OUT`, `SoilOrg.OUT`, `N2O.OUT`, and `WaterBal.OUT` fields.
- [ ] Re-run all LowInput multi-observation cultivars with constrained AgMIP
  Step 7 before exporting the final optimized cultivar directory.
- [ ] Extend the validated Tensift IA55 training database to the remaining
  sowing-date, irrigation, and nitrogen treatments.
- [ ] Move DSSAT automatic-irrigation parameters (including `ITHRL`) from global
  model defaults to simulation-specific policies.
- [ ] Extend prefetched data access to STICS v11 initial conditions (`ficini`).
- [ ] Replace broad periodic cache clearing with bounded caches where memory
  measurements show it is useful.

## Tests and maintenance

- [ ] APSIM weather (`apsimweatherconverter.py`) still reads `tav` and `amp`
  only from ModelsDictionary; use `Coordinates.tav`/`amp` first, as DSSAT does.
- [ ] Audit remaining APSIM catalogue inputs with public setters against
  runtime assignments, especially state properties in structure and volatilisation.

- [ ] Validate the shared APSIM NG catalogue categories and parameter coverage
  (including official management-rule parameters) against a reference .apsimx,
  then select converter-supported rows before importing into ModelsDictionary.

- [ ] Align APSIM initialization organic FOMCNRatio with the soil export's
  ParameterResolver value instead of its separate hard-coded 40.0 fallback.

- [ ] Validate APSIM generated soil profiles with the APSIM executable,
  using measured `Ssat` or explicitly configured `Physical.SAT`.

- [x] Resolve CELSIUS V32 soil defaults and apply generic per-soil overrides
  for any matching `Soil` parameter in ModelsDictionary.
- [x] Populate CELSIUS V32 `Soil.CsurNhum` from
  `MasterInput.Soil.OrganicC / OrganicNStock`.
- [ ] CELSIUS V32 engine (Access VBA, then pipeline): organic fertilisation
  still fails after the table-name fix. `FertiOrgaClass.sTypeMorga` is declared
  `As Double` but compared with the text `"indetermine"` (InvalidCastException),
  and `ApportsOrgaClass` looks up `ListResidus.TypeMorga`, a column the table
  does not have (`CodeRes`). Decide how MasterInput `TypeResidues` maps to the
  CELSIUS residue codes in the converter.
- [ ] CELSIUS V32 integration test: mineral inputs are applied (`AppMinNj`) but
  change nothing while `OptionsModel.ActiveNstress = 0`; add a fixture
  simulation option with nitrogen stress enabled for the fertilised scenario.
- [ ] DSSAT standard: a `STOP 99` in one simulation aborts its whole chunk and
  the main loop discards the chunk, including simulations that already
  succeeded; skip only the failing simulation and report it.
- [ ] Make the text fixtures runnable by every model and add opt-in
  `integration` tests that run the executables: extend the fixture weather to
  2004 for the DSSAT successive rotation, version the STICS cultivar files
  and DSSAT genotype files, then start with a CELSIUS V32 run.
- [x] Commit the five pending `migrations/*.sql` schema scripts that `AGENTS.md`
  requires (ssat, coordinates tav/amp, overrides numlayer, drainfao, ssks),
  done in `2002ae50` together with their tests. The `.gitignore` rule blamed
  before never existed any more: `git check-ignore` confirms the scripts were
  not ignored, only uncommitted. That commit also documents the
  `tests/stics_successive/ModelsDictionaryArise.db` migration (CELSIUS `Soil`
  defaults in `Default_Value_Datamill`).
- [ ] Decide what to do with `docs/stics/` (572 KB of generated HTML reference
  for the STICS v11 soil and plant parameters), still untracked: version it,
  move it out of the repository, or add it to `.gitignore`.
- [ ] Renormalize the 19 files still stored as CRLF under `notebooks/`,
  `migrations/` and `tests/` (`git add --renormalize`), once the soil work in
  progress on those paths is committed. The 20 files outside them were done in
  `d6be03fc`.
- [x] `tests/test_tempopar.py` and `tests/test_tempoparv6.py` called `export()`
  with an outdated signature (`usmdir` missing, and a `Connection` passed where
  `write_file` expects a directory). Both are now real tests on the text
  fixtures: tempopar is parametrized over the four stress combinations to pin
  the 1/2 activation codes and checks the fixed part resolved by
  `common_tempopar`, tempoparv6 checks that `common_tempoparv6` resolves the
  st_tempoparv6 rows and that the converter writes them verbatim.
- [ ] Add a reference MasterInput input schema to the package and a test that
  keeps `tests/fixtures/sources/masterinput/schema.sql` identical to it.
- [ ] Add more named scenarios to the text MasterInput fixture: two soils,
  point overrides.
- [ ] Move converter tests from the per-model fixture databases to the
  `masterinput_db` / `masterinput_copy` pytest fixtures. Done for
  `test_sticsconverter.py`, `test_dssatconverter.py`, `test_tempopar.py`,
  `test_tempoparv6.py`, `apsim/test_apsim_converter.py` and
  `apsim/test_management_with_real_db.py`; `test_celsiusconverter.py` and
  `apsim/test_apsim_main.py` still convert the committed databases in place.
- [ ] Republish `celsiusV32` from the optimized Celsius ADODB layer and check a
  two-crop association run writes identical `OutputD_2` rows before and after.
- [ ] Regenerate `tests/celsius/output_v32_standard/celsius_v32_standard.db`
  (still uses `__TECH` technique identifiers) and document the fixture migration.
- [ ] Add mineral and organic fertilisation cases to the CELSIUS V32 standard
  and successive fixtures and verify that `celsiusV32` applies the inputs
  (the Access reference has `fertiminON` and `fertiorgON` disabled everywhere).
- [ ] Validate CELSIUS V32 generated databases end to end against the Access
  V32 reference for standard, associated-crop, and successive simulations.
- [ ] Extend CELSIUS V32 `SummaryOutput` import to expose the second crop of an
  association without losing `PlantOrder` identity.
- [ ] Add an end-to-end DSSAT regression run proving that standard dates keep
  the legacy extended-DOY convention and successive SQX dates use
  `SowingYearOffset`.
- [ ] Define a realistic automatic-irrigation threshold (`ratiol`) and related
  management overrides before using the fixture for agronomic validation.
- [ ] Add a non-zero irrigation fixture case and verify the generated
  `fictec1.txt` in a standard STICS v11 run.
- [ ] Add a multi-point standard STICS v11 regression test proving that the
  station cache does not reuse `PointParameterOverrides` across `idPoint`.
- [x] Run the complete pytest suite in an environment containing the project
  development dependencies. Use the `agrometflow` conda environment, which has
  `joblib` and `modfilegen` installed editable on the working tree; the conda
  `base` environment has no `joblib` and leaves 8 modules uncollectable.
  Baseline on 2026-11-26: **306 passed, 2 skipped** (the two opt-in engine
  tests), run as `~/miniforge3/envs/agrometflow/bin/python -m pytest tests/
  -o addopts=""`. `-o addopts=""` is needed because `pytest-cov` is absent
  while `pyproject.toml` sets `--cov=modfilegen`; add `pytest-cov` to that
  environment to run the suite with coverage.
- [ ] `tests/test_celsiusconverter.py` still mutates the committed
  `tests/data/CelsiusV3nov17_dataArise.db` in place: it comes back modified
  (same size, different bytes) after the suite and has to be restored with
  `git restore`. The converters write to their input database (`export()`
  issues `CREATE INDEX IF NOT EXISTS` and sets `PRAGMA journal_mode = WAL`),
  so the test has to convert a copy. This breaks the `AGENTS.md` rule against
  undocumented fixture changes and makes any CI run dirty. The adapted
  converter tests already use the `masterinput_copy` / `legacy_*_copy`
  fixtures for exactly this reason; `tests/apsim/test_apsim_main.py` should
  follow, as it converts `MasterInput_bon_test.db` directly.
- [x] Fix the four legacy test modules that failed on a pristine checkout for
  API drift rather than a code defect. All four now run on the text fixtures:
  - `tests/apsim/test_apsim_converter.py` imported `Converter...` from the
    pre-package layout and called `export()` with five keyword arguments it
    does not take; it now pins the real `export(MasterInput, ModelDictionary)`
    contract (indexes dropped first, then recreated; WAL; and the indexes
    APSIM deliberately does not create, unlike STICS and DSSAT);
  - `tests/test_sticsconverter.py` imported a `SticsConverter` class that no
    longer exists; it now covers v9 simulation selection, `chunk_data`
    partitioning and index creation;
  - `tests/test_sticsconverter2.py` and `tests/test_dssatconverter.py` called
    `main()` with an unconfigured `GlobalVariables`; the engine runs moved
    behind the new `integration` marker, and `test_dssatconverter.py` also
    covers the chunking, the indexes and the rejection of an unsupported
    DSSAT version.
- [x] The three APSIM tests that failed on `ListCultivars.SpeciesName`. The
  shared schema always had the column: `test_database_integration.py` declared
  its own in-memory `ListCultivars` with `CropName`, and
  `test_management_with_real_db.py` pointed at an absolute path on another
  machine (`/mnt/d/Mes Donnees/TCMP/github/...`). The first now uses
  `SpeciesName`, the second runs on the `masterinput_db` fixture.
- [ ] Extend the opt-in `integration` marker (`--run-integration`, see
  `tests/conftest.py`) to APSIM, CELSIUS v3 and CELSIUS V32, and to the
  successive runs; only STICS v9 and DSSAT standard are covered so far.
- [ ] Add end-to-end tests proving that simulations sharing an `idSoil` reuse
  prefetched soil data and generated soil-file content.
- [ ] Add regression tests for default, computed, and explicit `q0` values.

## Completed

- [x] Align DSSAT initial-condition `SH2O` with effective whole-soil `SLLL`
  and `SDUL`, including shared fine-earth correction, layer/profile `SLCF`
  fallback and explicit DSSAT overrides in standard and successive generation.

- [x] Express shared fine-earth organic C and total N concentrations as DSSAT
  whole-soil-equivalent `SLOC` and `SLNI` using `(1 - SLCF/100)` for simple
  and detailed soils, while preserving explicit DSSAT layer overrides.

- [x] Express shared fine-earth volumetric water limits as DSSAT whole-soil
  `SLLL`, `SDUL` and `SSAT` using `(1 - SLCF/100)`, without changing fine-earth
  bulk density or explicitly overridden DSSAT values.

- [x] Correct CELSIUS V32 `Soil.StockN`, whose shared `OrganicNStock` input is
  measured on fine earth, by the depth-weighted fine-earth volume fraction
  over CELSIUS's fixed 0-30 cm organic-N layer; explicit model overrides still
  take precedence.

- [x] Runoff types are text codes: `soil_repository.runoff_type_code` maps 2,
  2.0 and '2' to '2'; `SoilDataRepository` attaches `RunoffCoefBSoil` and
  `CurveNumber` by that code (no SQL join on mixed types), CELSIUS V32 uses it
  for `TypeRui`, STICS v9 joins on text, and the fixture declares
  `Soil.RunoffType` TEXT.

- [x] CELSIUS V32 `Soil.TypeRui` is the `RunoffTypes.CodRunoffCelsius` of the
  soil's `RunoffType` (for example 2 -> 6), instead of the MasterInput code
  itself; a type without a CELSIUS code is an error, and databases without the
  column keep the previous behaviour.

- [x] DSSAT crop model and experiment-file extension use the current crop
  `ListCultOption.CG` + `DSCROP` (for example `MZCER048`) instead of the
  previous crop `PRCROP`, which only feeds the initial-condition `PCR`.

- [x] Document the configuration in `docs/source/configuration.rst`: global
  options with values and defaults, `albedoStrategy` and `sticsv11Q0Strategy`,
  soil parameter priority rules (overrides, `NumLayer`, measured properties,
  `Ssat`, `Ssks`, `DrainFAO`, `tav`/`amp`) and weather coverage.

- [x] Global option `albedoStrategy` (`"measured"` by default, or
  `"texture"`): with `"texture"`, the soil albedo is re-estimated from
  `Soil.SoilTextureType` (`TEXTURE_ALBEDO`, else 0.30) in `SoilDataRepository`,
  so every converter reading soils through it uses the same albedo; STICS v9
  `param.sol`, which still queries `Soil` directly, applies the same rule.

- [x] `Soil.DrainFAO` (FAO drainage class 1 to 7,
  `migrations/20261024_add_soil_drainfao.sql`); DSSAT SLDR uses the `sldr`
  override, else the FAO class (0.01, 0.05, 0.25, 0.40, 0.60, 0.75, 0.85),
  else the ModelsDictionary default.

- [x] Measured saturated hydraulic conductivity: `Soil.Ssks` and
  `SoilLayers.Ssks` in cm/h (`migrations/20261024_add_soil_ssks.sql`). DSSAT
  SSKS and APSIM KS (x 240 mm/day) use override, then layer measure, then soil
  measure, then the default; a simple soil now uses `Soil.Ssks`.

- [x] DSSAT soil files (standard and successive) read soils through
  `SoilDataRepository`, parameters through `ParameterResolver` (tables
  `dssat_soil_site` and `dssat_soil_data`, with layer-wise overrides) and
  coordinates through `CoordinateResolver`, prefetched once per chunk; the
  XX.SOL cache key is now soil, point and site code, so two points sharing a
  soil and a management no longer reuse each other's coordinates. Output is
  unchanged without overrides.

- [x] APSIM soil arrays use layer-wise overrides through
  `ParameterResolver.resolve_layers()`; `has_override(..., layer=k)` keeps
  measured properties unless an override applies to that layer, and layer
  overrides on scalar properties (for example `FOMCNRatio`) are rejected.

- [x] Layer-wise soil overrides: `SoilParameterOverrides.NumLayer` (0 = whole
  profile, 1..n = layer; `migrations/20261023_soil_parameter_overrides_numlayer.sql`),
  `ParameterResolver.resolve_layers()` (layer, else profile, else default; errors
  for a missing layer or a layer override on a whole-soil parameter), used by
  STICS v11 `param.sol` for `typecailloux`, `infil` and `epd`.

- [x] Merge `tests/stics_successive/test_sticssuccessiveconverter.py` into
  `tests/test_sticssuccessiveconverter.py` on the text fixture; the season test
  now checks the current rule (each season ends the day before the next season's
  first operation, so it covers the fallow after its own harvest).

- [x] DSSAT weather files (standard and successive) take TAV and AMP from the
  optional `Coordinates.tav`/`amp` columns when filled, and fall back to the
  ModelsDictionary defaults otherwise (`migrations/20261023_add_coordinates_tav_amp.sql`).

- [x] Clarify APSIM tillage cn_rain as the cumulative rainfall threshold (mm)
  cancelling the tillage-induced Curve Number reduction, documenting its
  linear decay and PotentialRunoff accumulation with upstream code evidence.

- [x] Correct APSIM FinalLeafNo and dynamic volatilisation pH as outputs,
  remove their false input rows, and preserve runtime-assignment evidence
  in the generator and regenerated catalogue; retain chemical.PH as input.

- [x] Extend the APSIM NG dictionary with residue types, tillage and public
  parameters/variables from 23 official management rules, including automatic
  sowing, irrigation and fertilisation; exclude methods and keep toolbox
  sample settings separate from generic defaults.

- [x] Replace the APSIM NG API inventory with functional input categories
  and shared outputs, remove technical types and crop-specific resource rows,
  and disambiguate incompatible homonyms without inventing generic defaults.

- [x] Build a separate APSIM NG Variables CSV from pinned official C# metadata
  and JSON resources, preserving the 22-column dictionary schema, explicit
  defaults and provenance without reusing legacy APSIM rows or changing a DB.

- [x] Require APSIM soil export FOMCNRatio from ParameterResolver
  (Organic defaults and per-soil overrides), with explicit missing-parameter
  failure and no fixed fallback in the MasterInput soil export.

- [x] Derive APSIM Organic.SoilCNRatio from Soil.OrganicC / OrganicNStock
  (same units), preserve explicit overrides, and require configured values
  when the soil ratio cannot be calculated.

- [x] Map APSIM Physical.Rocks to cf and Physical.Texture to SoilTextureType,
  with layer-to-soil fallback and string-safe explicit texture overrides.

- [x] Populate APSIM ParticleSizeSand/Silt/Clay from layer sand/silt/clay,
  falling back to Soil when the layer column or value is missing, including
  compatibility with databases without SoilLayers.Sand.

- [x] Simplify APSIM soil JSON construction with explicit layer lists:
  pass MasterInput OrganicC/pH directly and keep optional DataFrame column
  handling in export_simple's adapter; remove the unused database builder.

- [x] Align APSIM soil export with STICS v11: require preloaded
  `ParameterResolver` and `SoilDataRepository`, remove database arguments and
  internal service creation, and verify export executes no SQL queries.

- [x] Require the known `id_soil` in APSIM soil export and remove redundant
  simulation lookup and path-based identifier extraction.

- [x] Clarify the APSIM soil export docstring, including arguments,
  prefetch requirements, returned file path and main errors.

- [x] Remove the APSIM porosity-based saturation estimate; fail explicitly
  when neither MasterInput `Ssat` nor configured `Physical.SAT` is available.

- [x] Read APSIM soils from MasterInput `Soil` / `SoilLayers` by simulation
  `idsoil`, convert depths and water percentages, resolve model defaults and
  soil overrides, and fix soil-file generation, embedding and batch reuse;
  cover the mapping with shared text-fixture regression tests.

- [x] Support layer-specific `SoilLayers.Ssat` in DSSAT with fallback to `Soil.Ssat` and then layer `Wfc`, without confusing saturation (`SSAT`) with saturated conductivity (`SSKS`).

- [x] Repeat CELSIUS V32 and DSSAT successive `CropManagement` patterns independently for each `idsim` until the next occurrence falls after the `SimUnitList` end, matching STICS v11 cycle expansion.

- [x] Align DSSAT 4.8 successive season boundaries with STICS v11: derive years from `SeasonYearOffset`, start each later season at its first management operation, end the preceding season one day earlier, preserve the global first and last bounds, and ignore `DHarvest` when partitioning the rotation.

- [x] Align CELSIUS V32 successive season boundaries with STICS v11: derive years from `SeasonYearOffset`, use the next season's first management operation as the boundary, retain the global `SimUnitList` bounds, and ignore `DHarvest` when partitioning rotations.

- [x] Align STICS v11 successive synthesis with the configurable output pipeline: generate `rap.mod` from the active selection, write canonical selected columns to CSV and `SummaryOutput`, and preserve associated crops through `(Idsim, SeasonOrder, PlantOrder)` with `P`/`A` roles.

- [x] Derive STICS v11 successive season boundaries from the next season's first management operation, using `SeasonYearOffset` for its year; keep the first and last bounds from `SimUnitList` and stop using `DHarvest` to partition rotations.

- [x] Add the `FERT_MIN_ORG` fertilisation scenario to the MasterInput fixture
  (`SCN_fert_min`, `SCN_fert_org`) and check its CELSIUS V32 conversion.

- [x] Drop DSSAT daily output rows outside StartYear/StartDay to
  EndYear/EndDay (standard and successive), so days DSSAT simulates after the
  simulation end, possibly on rollover weather, never reach `DssatDailyOutput`.

- [x] Skip, without deleting them from `SimUnitList`, the simulations whose
  StartYear/StartDay to EndYear/EndDay period is not covered by consecutive
  `RAclimateD` days of their `idPoint` (`modfilegen.weather_coverage`), in every
  converter; skipped simulations are printed and listed in
  `skipped_simulations_<model>.csv` in the output directory.

- [x] Add a `modelsdictionary` text fixture (`Variables` table only, exported
  from `LowInput/blindphase_corrected/ModelsDictionaryArise.db`) and the
  `modelsdictionary_db` pytest fixture.

- [x] Move `test_celsius_v32_converter.py` to the text fixtures: MasterInput
  cultivars map to CELSIUS V32 codes, and a reduced CELSIUS V32 template is
  versioned in `tests/fixtures/sources/celsius_v32_template`.

- [x] Align the text MasterInput fixture with the LowInput reference input schema
  (`migrations/20261003_align_masterinput_with_lowinput_schema.sql`) and let
  DSSAT successive read `SeasonYearOffset`, keeping `SowingYearOffset` as a
  legacy fallback like STICS v11 and CELSIUS V32.

- [x] Move `test_dssatsuccessiveconverter.py` to the `masterinput_db` text
  fixture, selecting the `ROT_MAIZE_PEANUT_3Y` rotation, and expect the extra
  boundary weather year for its day-120 start.

- [x] Align DSSAT successive synthesis with the standard DSSAT configurable
  pipeline: retain raw `Summary.OUT` fields, transform them through the active
  output selection with per-run `SDAT` date context, and write the same
  canonical columns to CSV and `SummaryOutput` for both `dt` modes.

- [x] Base DSSAT successive summary time and every phenological date on each
  model-estimated `Summary.OUT` `SDAT`, including cross-year and leap-year
  offsets for both implicit repeated cycles and explicit management seasons.

- [x] Resolve DSSAT successive latitude and longitude exclusively from the
  `Coordinates` row linked by `idPoint` for both `dt` modes, leaving missing
  coordinates null without parsing `Idsim`.

- [x] Use the shared `CoordinateResolver` in standard DSSAT for both `dt`
  modes, with `StartYear` as `time` and no coordinate parsing from `Idsim`.

- [x] Use the shared `CoordinateResolver` in STICS v9, STICS v11 standard and
  successive, CELSIUS v3, and CELSIUS V32; all summary CSV and database paths
  now source `lat`/`lon` from `Coordinates` independently of `dt`.

- [x] Make every converter write `SummaryOutput` the same way through
  `OutputConfiguration.replace_model_summary_rows`: create or extend the table,
  replace only the current model's rows; DSSAT successive and STICS v11 no
  longer fail when the table is missing.

- [x] Version the MasterInput test fixture as text (`tests/fixtures/sources/masterinput`:
  `schema.sql` plus one CSV per input table), rebuilt per pytest session; the
  initial export from `tests/stics_successive/MasterInput.db` round-trips exactly.

- [x] Use the simulation identifier as the CELSIUS V32 `IdTech_Com`, dropping
  the `__TECH` suffix to match the Access V32 convention.

- [x] Fix the CELSIUS V32 engine fertilisation reading in the CelsiusV32
  repository: read `FertiOrga_List` instead of `FertiOrg_List`, and check
  `IdTech_Com` against `sIdTec` instead of `sIdSim` for mineral and organic
  inputs; Access/VB.NET regression passes on Windows and Linux.

- [x] Populate lon, lat and time in canonical CELSIUS outputs for dt=1 by
  decoding the shared lat_lon_year simulation identifier convention.

- [x] Write canonical selected outputs to a Celsius CSV independently of dt,
  while keeping OutputSynt as the raw model output.

- [x] Canonicalize STICS result CSV files for both dt modes and preserve
  canonical rows consistently when resuming an interrupted run.

- [x] Document packaged and user-provided output catalogues, named output
  selections, the default legacy selection, and model availability rules.

- [x] Replace CELSIUS v3 and v32 hard-coded SummaryOutput mappings with the
  shared configurable transformation and map transpiration from SigmaTranspiMC.

- [x] Rewrite DSSAT standard result CSVs with canonical shared-variable columns only, while keeping raw `Summary.OUT` fields internal to transformation.

- [x] Write STICS standard result CSVs with canonical selected columns only, keeping raw model fields in an internal temporary CSV and preserving resume compatibility.

- [x] Map DSSAT fresh yield from `FHWAM` (kg/ha) to `FreshYield` (t/ha), treating only the DSSAT `-99` sentinel as missing and preserving zero.

- [x] Replace DSSAT standard hard-coded `SummaryOutput` mappings with the shared configurable transformation for `Summary.OUT`.

- [x] Mark STICS v9 end-of-cycle `msrac(n)` as invalid for `RootBiomass`, pending derivation from daily output.

- [x] Validate the expanded configurable `rap.mod` against the STICS v9 executable, including derived soil mineral N from `azomes + ammomes`.

- [x] Support derived multi-field output mappings and map STICS v9 soil mineral N as `azomes + ammomes`, aligned with STICS v11 `SMNmes`.

- [x] Transform STICS v9 report fields through the shared output catalog and dynamically extend and populate `SummaryOutput` from the selected variables.

- [x] Generate STICS v9 `rap.mod` from the configured output selection, excluding unavailable, invalid, and duplicate mappings while preserving template control lines.

- [x] Remove the obsolete universal-wheel setting so Python-3-only wheels are tagged correctly.

- [x] Add the common output configuration service: load and validate the three packaged YAML catalogs, resolve selections and model mappings, apply generic conversions, and create or extend `SummaryOutput`.

- [x] Run CELSIUS V32 simulations in parallel (`nthreads`) on reduced
  per-process copies that keep successive chains whole, merge outputs in
  simulation order, and index the per-simulation lookups at conversion.

- [x] Make CELSIUS V32 runs usable on the full standard fixture: fix the
  `phenoCTphot` stage overflow on crop death (Celsius VBA), write daily output
  only when `dailyoutput == 1`, and make the Celsius ADODB layer append daily rows without
  reloading the table, in one transaction per simulation.

- [x] Add a native CELSIUS V32 converter that replaces the Datamill mapping,
  supports standard and successive `SeasonOrder`, preserves two-crop
  associations through `PlantOrder`, converts dated management operations,
  runs `celsiusV32`, and imports first-crop synthesis outputs.

- [x] Rebuild the empty DSSAT successive `IrrigationFOperations` fixture table
  with the shared LowInput schema and lookup indexes.

- [x] Make STICS v11 successive single-offset patterns repeat annually, with
  each seasonal end equal to sowing plus `DHarvest`, capped by the global end.

- [x] Document the three-hour Morocco rainfed-wheat training protocol covering
  four climate-sensitivity scenarios, DSSAT execution, paired yield inference,
  interpretation limits, and participant deliverables.

- [x] Extend the Morocco climate-training notebook with scenario-specific
  phenology, phase-resolved DSSAT water stress, and reproductive heat-exposure
  analyses validated against the 30-season successive outputs.

- [x] Add a reusable migration for the soil, crop-management, and point
  parameter override tables and their required unique lookup indexes.

- [x] Keep DSSAT standard date handling unchanged while making successive SQX
  management dates honor `StartYear + SowingYearOffset`.

- [x] Read DSSAT `SSAT` from the shared soil-level `Soil.Ssat` value, with
  backward-compatible fallback to `Soil.Wfc * 1.01 / 100`.

- [x] Retain LowInput cultivar initial parameters whenever calibration does
  not strictly improve the global `imats` MSE, while preserving raw optimizer
  values for diagnostics.

- [x] Preserve each LowInput cultivar's initial `stdrpmat/stlevdrp` ratio
  during every STICS evaluation in AgMIP Step 7.

- [x] Rebuild the LowInput cultivar optimization summary from both newly
  selected runs and previously saved per-cultivar RDS results.

- [x] Make the LowInput sorghum/millet calibration start one repetition from
  each cultivar's initial `stlevdrp` and use the Linux STICS binary that
  correctly applies `param.sti` forcing.

- [x] Export all STICS technical intervention tables to the summary workbook,
  including dynamic `julapI_n` and `doseI_n` irrigation columns.

- [x] Synchronize LowInput copied STICS cultivar filenames, database cultivar
  codes, and internal `codevar` values.

- [x] Import LowInput STICS `codlocirrig` management overrides from observed
  irrigation types.

- [x] Accept repeated STICS intervention-table headers when converting
  irrigated `fictec` text files to XML.

- [x] Import LowInput manual irrigation schedules from
  `data_corrected/irrigated_amount.xlsx` as sowing-relative operations while
  preserving rainfed managements.

- [x] Split LowInput STICS cultivars by GDD class and observed cultivar name,
  with shared variants for identical names and collision-safe suffixes.

- [x] Add the explicit ZIM_I1 (GDD 2000) and ZIM_I2 (GDD 1900) STICS
  cultivar variants for sites absent from `GDD_site.csv`.

- [x] Move STICS v11 `interrang` values from the shared `CropManagement`
  schema to model-specific `fictec1`/`fictec2` management overrides.

- [x] Keep STICS v11 albedo in the physical `Soil.albedo` column rather than
  treating it as a `SoilParameterOverrides` parameter.

- [x] Add generic `PointParameterOverrides`, preload them by `idPoint`, and
  apply them to every dictionary-backed STICS v11 `station` parameter.

- [x] Separate the standard STICS v11 soil and station caches so station files
  are keyed by `idPoint` and mixed-crop status.

- [x] Seed the successive STICS fixture with a `codecalirrig = 1` override for
  season 3 of `ROT_MAIZE_PEANUT_3Y`.

- [x] Add prefetched, model-specific crop-management parameter overrides keyed
  by `(idMangt, SeasonOrder, PlantOrder)` for every dictionary-backed STICS v11
  `fictec1` and `fictec2` parameter.

- [x] Force `codecalirrig = 2` and `codedateappH2O = 2` whenever STICS v11
  manual irrigation operations are generated.

- [x] Verify a complete three-season STICS v11 successive run containing
  rainfed seasons and a season with three manual irrigation interventions.

- [x] Fix STICS v11 manual-irrigation serialization by repeating the table
  header before every intervention, as required by the STICS text reader.

- [x] Integrate prefetched, sowing-relative `IrrigationFOperations` into the
  standard and successive STICS v11 input-generation paths.

- [x] Extend the STICS successive MasterInput fixture with the documented
  `IrrigationFOperations` schema for sowing-relative date and irrigation dose.

- [x] Finalize generated climate-training databases with an explicit SQLite
  WAL checkpoint, DELETE journal mode, and closed connections.

- [x] Add a validated training notebook that derives HIST, +2 °C, −20% rain,
  and combined climate-sensitivity databases from a source MasterInput, with
  a common monthly-climatology comparison figure and an initial four-scenario
  yield-distribution analysis plus paired annual absolute and relative yield
  differences against HIST, 95% confidence intervals, paired t/Wilcoxon tests,
  and Holm multiple-comparison correction.

- [x] Export the extra boundary weather year required by DSSAT successive
  sequences that start after January 1.

- [x] Allow textual irrigation and inorganic-fertilization policy identifiers
  in DSSAT successive treatment levels.

- [x] Migrate the Tutorial `MasterInput.db` fixture with the management and
  cultivar columns required by standard and successive DSSAT simulations.

- [x] Create and validate the initial 30-season Tensift wheat training case
  with cultivar Karim and the global IA55 automatic-irrigation rule.

- [x] Add `ParameterResolver.prefetch()` for STICS v11 `paramsol` defaults and
  soil-specific overrides.
- [x] Add `SoilDataRepository` for prefetched `Soil`, `RunoffTypes`, and
  `SoilLayers` data.
- [x] Add the global STICS v11 `q0` strategy with explicit overrides taking
  priority.
- [x] Share the STICS successive `param.sol` cache within each worker batch.

## Working convention

Move completed items to **Completed** rather than deleting them. Review this
file before starting a feature and after finishing one. Tasks that become large
should be moved to an issue while retaining a short link here.
