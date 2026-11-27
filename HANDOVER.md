# Handover: the `cross-platform` branch

For whoever picks this up next, human or agent. `TODO.md` is the live task
list; this file is the context that `TODO.md` does not carry — why things
are the way they are, what is already settled, and what will bite you.

Branch `cross-platform`, tracking `origin/cross-platform` on GitHub
(`CropModelingPlatform/ModFileGen`), branched off `stics`. For the shape of
the work, `git log --oneline origin/stics..HEAD` — the commit messages carry
the reasoning for each change and are worth reading before touching the area
they describe. Read `AGENTS.md` first: it is the repository's own instruction
file and it takes precedence over this one.

## What the work is for

Students must be able to run ModFileGen on **Windows and macOS with no
administrator rights and no WSL**, because the AgriscaleContainer needs
Docker Desktop, which needs both. That is the whole reason this branch
exists.

Two constraints the user set explicitly and that still hold:

- **Do not lose computational performance.** The parallel path is the
  product. Measure before and after anything that touches it.
- **Do not commit the user's adapted tests** — 18 modified files are
  deliberately left out (`tests/conftest.py`, `tests/apsim/*`,
  `tests/test_sticsconverter*`, `tests/test_tempopar*`, the notebooks, two
  `tests/data/*.db`). They are "lot A". Ask before committing any of them. A
  fresh clone therefore has the 574 tests written on this branch but not
  those adaptations. `docs/stics/` is also untracked and is a separate
  question, already in `TODO.md`: 572 KB of generated HTML reference.

## How to work here

```bash
conda run -n agrometflow python -m pytest -q -o addopts=""
```

The `agrometflow` environment is the one with the dependencies; `base` lacks
`joblib`. The `-o addopts=""` is needed because `pyproject.toml` adds
`--cov=modfilegen`, and `pytest-cov` is not always installed. Expect
**574 passed, 3 skipped**.

Engines live at `/opt/stics/bin`, `/opt/sticsv11/bin`, `/usr/bin/dssat`,
`/usr/bin/dssatv48`, `/usr/share/apsim`, `/usr/share/celsius*`. All eight
report `ok` here, so end-to-end runs are possible on this machine.

A Windows copy of the tree is at `/mnt/c/Users/midingoyi/ModFileGen`. It was
kept in step by file copies; now that the branch is pushed, `git pull` there
is the better route.

### Run something

```bash
conda run -n agrometflow python -m modfilegen.cli selftest
conda run -n agrometflow python -m modfilegen.cli fixture --out /tmp/demo
conda run -n agrometflow python -m modfilegen.cli run --model stics --version v11 \
    --mode successive --master-input /tmp/demo/masterinput.db \
    --models-dictionary /tmp/demo/modelsdictionary.db \
    --cultivars src/modfilegen/data_fixtures/cultivars/stics \
    --out /tmp/out --manifest /tmp/out.sha256
```

The STICS v11 successive run on the packaged fixture must produce exactly:

```
edc6ce001b02919148e2c493bee4cea7f66d2fdb5536b13c79f97b1a47347c21  <run-id>_stics_successive.csv
```

That digest is the single best regression check in the repository. It is
stable across LF and CRLF plant files, across the repository fixture and the
packaged one, and across a wheel install outside the tree.

DSSAT v4.8 successive on the same fixture gives `10 crop-seasons requested`,
six declined as associations, **4 produced**, exit 0.

## What was added

| file | what it is |
|---|---|
| `src/modfilegen/engine_runner.py` | starts an engine; replaced 7 bash scripts; 14.65 ms → 1.04 ms per launcher |
| `src/modfilegen/engines.py` | one resolution cascade for 8 executables, plus `inspect()` for the report |
| `src/modfilegen/text_files.py` | one encoding policy for 44 `open()` sites: UTF-8, LF on write, lenient decode of engine output |
| `src/modfilegen/paths.py` | `path_parts()`, replacing 23 `split(os.sep)` |
| `src/modfilegen/cli.py` | `agriscale engines / run / fixture / selftest` |
| `src/modfilegen/run_command.py` | the `run` subcommand, crop-season accounting, sha256 manifest |
| `src/modfilegen/selftest.py` | checks an install with no engine |
| `src/modfilegen/fixtures.py` | the fixture builder, moved out of `tests/` so a wheel carries it |
| `src/modfilegen/data_fixtures/` | the demo CSVs, plant files and genotypes, 1.1 MB |
| `src/modfilegen/Converter/DssatConverter/applicability.py` | what DSSAT may be asked to simulate |

`tests/fixtures/build_fixtures.py` is now a shim re-exporting
`modfilegen.fixtures`, so `tests/conftest.py` (lot A, uncommitted) keeps
working untouched.

## Decisions already settled — do not relitigate

**A season ends the day before the next season's first cultural operation**,
not before its sowing. A season owns its pre-sowing operations. On the
fixture, season 2 irrigates ten days before sowing, so season 1 closes
eleven days before that sowing. Both STICS v11 and DSSAT implement this and
produce identical windows; `tests/test_successive_season_boundaries.py`
holds them to the rule and to each other. The user confirmed this reading
explicitly.

**A user's plant and genotype files are copied byte for byte** and never
decoded — CRLF, LF, cp1252, a byte-order mark, no final newline. Three
converters, `shutil.copyfile`/`copy`. A guard in
`tests/test_user_plant_files.py` refuses an `open()` on those paths: routing
them through `text_files` would look like tidying and would normalise line
endings and raise on non-UTF-8 input. Both engines were run on LF copies and
gave identical results, so the CRLF these files carry is a convention, not a
requirement.

**Per-crop-season parameter overrides go in `CropManagementParameterOverrides`**,
keyed by `(idMangt, SeasonOrder, PlantOrder)`. No new table was needed. The
fixture carries one row per model as a worked example, including
`dssat.dssat_x_simulation_method.MEPHO = L` on the peanut season. Only
`dssat_x_simulation_method` is wired (`OVERRIDABLE_TABLES` in
`dssatxconverter.py`); adding a table is one line plus a `prefetch_management`
call in the parent process.

**`NYERS` cannot bound a DSSAT sequence at a season count.** `CSM.for` uses
it once, at the first run, for `YRDOY_END = (year + NYERS) * 1000 + day - 1`,
then sets it to 1; the sequence ends only at that date and the treatment list
is cycled until then. The span is a whole number of years from the start day,
so slack after the last declared harvest is unavoidable — 133 days on the
fixture. The summary reader therefore drops a cycle sown past the
simulation's own end. Do not try to compute a cleverer `NYERS`.

**`DHarvest` caps the DSSAT harvest.** The season window was written as
`HDATE`, leaving the peanut 364 days in the field until CROPGRO refused it
(300 flower cohorts). `season_harvest_date()` now takes the window end while
it is shorter and sowing plus `DHarvest` when it is longer. The windows
themselves do not move. DSSAT needs no continuity: it starts the next run
the day after this one ends and simulates bare soil until that season's
sowing — verified in `CSM.for:388` and `plant.for:350`.

**A `SIMULATION CONTROLS` block is duplicated only when a control really
differs.** The `AUTOMATIC MANAGEMENT` section is written on every level
because DSSAT's reader needs it there, so its windows are made sequence-wide
*while their switch leaves them unused* (`PLANT`/`HARVS` other than `A`).
Turn a switch to `A` and the per-season values stand and the blocks differ
again — which is then correct.

**`*SOIL ANALYSIS` written from dictionary defaults is fine.** Every value is
`-99`, and `IPSLIN.for:358` treats anything above `-1.E-6` as an override, so
`XX.SOL` stands and DSSAT estimates organic carbon from texture where none is
given. The user confirmed that is expected behaviour.

**Zero organic carbon on the second `XX.SOL` layer is the simple soil
representation**, not a lost value: `Soil.SoilOption = 'simple'` writes two
lines, the declared `OrganicC` in the top 30 cm and zero below.

## Traps that cost time here

**A loky worker re-imports the package and sees only the `GlobalVariables`
defaults.** Anything a caller sets must be resolved in `main()`, in the
parent, and passed in. This is why `engines.resolve()` is called before the
workers start and why `prefetch_management` happens in the parent. Empirically
verified; do not assume module state crosses.

**STICS is never taken from `PATH`.** v9 and v11 ship the same
`stics_modulo` file name, so `PATH` cannot tell them apart and the wrong
version would run silently. `engines.ENGINES["stics_v9"].commands` is
deliberately empty.

**Engine companions are looked for beside the *real* file**, not the symlink:
`/usr/bin/dssat` links into `/usr/share/dssat`, where `DSSATPRO` lives.

**`DSSATPRO` holds absolute, platform-specific paths** (`C:\DSSAT48`,
`/usr/local/share/dssat48`). Unpack DSSAT elsewhere without editing it and the
engine starts, finds no data, and blames the data.

**The converters swallow per-simulation failures**: they print to stderr and
carry on. That is why `run_command` reconciles crop-seasons requested,
declined and produced, and fails on either a shortfall or a surplus. Without
that, a defect looks exactly like declined work. Keep that property.

**`with sqlite3.connect(...)` commits but does not close.** On Windows that
holds a lock. 19 such sites remain outside the CELSIUS V32 runner.

**Fixture rules.** `AGENTS.md` forbids changing a fixture without documenting
the migration. The sources are CSV under `src/modfilegen/data_fixtures`; the
provenance table is `tests/fixtures/README.md`. After a change, regenerate
the self-test digests with `modfilegen.selftest.write_reference()`.

## Where to go next

`TODO.md` has 49 open items. The ones that matter, in the order I would take
them:

1. **A generation-only mode.** The converters write a simulation's files and
   start the engine in the same loop, so there is no way to generate without
   an engine. Everything else waits on this: `agriscale selftest` cannot
   check generated files, and CI cannot run on a machine with no model. This
   is also where the weather cache pays, since no engine time hides it.
2. **CI matrix `windows-latest` / `macos-latest`.** macOS has never been
   tested by anyone. Blocked on two known things: `test_celsiusconverter`
   mutates `tests/data/CelsiusV3nov17_dataArise.db`, and that same test
   cannot fail — the CELSIUS v3 converter catches every exception and prints.
3. **Windows `MAX_PATH`.** Measure the longest path before generating and
   refuse with the overflow in figures. `--temp` already lets a caller
   shorten it by hand; `--delete-intermediate` is the switch that exercises
   the file-lock case.
4. **PyPI.** Both artefacts build and pass `twine check`; the distribution
   is named `agriscale` while the import package stays `modfilegen`. The
   version is still 1.0.0 and a PyPI version is never rewritten, so settle
   1.0.0 or 1.1.0 first. The upload needs the maintainer's token.
5. **The detailed soil path has no end-to-end coverage.** The fixture
   declares two `SoilLayers` rows for a soil whose `SoilOption` is `simple`,
   so they are never read. Setting it to `detailed` would exercise a path
   nothing tests — and an untested path is where the irrigation defect had
   been hiding.

## How the defects were actually found

Every DSSAT defect on this branch came from the user running a model and
reading the generated files, never from a test. The irrigation block invented
its values from the dictionary and the file looked entirely plausible. Assume
the same of anything not yet run.

Two things I reported before verifying them properly, both corrected in the
commits: a "lost" organic carbon value that was the simple soil
representation, and a 1.11 s speed gain that was noise across a single pair
of runs. Repeat a measurement before reporting it, and check whether a
surprising value is a convention before calling it a bug.
