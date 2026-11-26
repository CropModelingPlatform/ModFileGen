"""Where MEPHO stands: the row, the resolver, the generated file."""
import sqlite3
import sys
from pathlib import Path

master = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/MasterInput.db")
dictionary = Path(sys.argv[2] if len(sys.argv) > 2 else "runs/ModelsDictionary.db")
out = Path(sys.argv[3]) if len(sys.argv) > 3 else None

print(f"1. the override row in {master}")
mi = sqlite3.connect(str(master))
rows = mi.execute(
    "SELECT idMangt, SeasonOrder, PlantOrder, TargetTable, Parameter, Value"
    " FROM CropManagementParameterOverrides WHERE lower(Model)='dssat'"
).fetchall()
if rows:
    for row in rows:
        print("   ", row)
else:
    print("   NONE. Add it -- and note the fixture build rebuilds from the")
    print("   CSV sources, so building again after inserting wipes it.")

print(f"\n2. what the resolver answers, per season")
try:
    from modfilegen.Converter.DssatConverter import dssatxconverter
    from modfilegen.parameter_resolver import ParameterResolver

    md = sqlite3.connect(str(dictionary))
    resolver = ParameterResolver(md, mi)
    resolver.prefetch_management(
        "dssat", dssatxconverter.OVERRIDABLE_TABLES, ["ROT_MAIZE_PEANUT_3Y"]
    )
    for season in (1, 2, 3):
        values = dssatxconverter.simulation_overrides(
            resolver, "ROT_MAIZE_PEANUT_3Y", season, 1
        )
        print(f"    season {season}: MEPHO = {None if values is None else values.get('mepho')}")
    md.close()
except Exception as error:
    print(f"    could not ask the resolver: {type(error).__name__}: {error}")
mi.close()

if out is None:
    print("\n3. pass the output directory as a third argument to check the file")
    raise SystemExit

print(f"\n3. the generated sequence file under {out}")
found = sorted(Path(out).rglob("ITSA1301.SQX"))
if not found:
    print("    no ITSA1301.SQX yet; run agriscale first")
    raise SystemExit
text = found[0].read_text(encoding="utf-8", errors="replace")
print(f"    {found[0]}")
print(f"    METHODS blocks: {text.count('@N METHODS')}")
print(f"    AUTOMATIC MANAGEMENT sections: {text.count('AUTOMATIC MANAGEMENT')}")
for line in text.splitlines():
    stripped = line.strip()
    if stripped[2:4] in ("ME", "PL") and stripped[:1].isdigit():
        print("   ", line.rstrip())
