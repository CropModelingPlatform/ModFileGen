#!/usr/bin/env bash

OLD_PWD="${PWD}"

USM_DIR="$1"
input_dir="$2"
dt=$(echo $3 | awk '{print int($1)}')
vstics="$4"
nbplt="$5"

cd "$USM_DIR"

sed -i -z 's/codeseprapport\n1/codeseprapport\n2/g' "$USM_DIR"/tempopar.sti

# check if vstics == "v9"
if [ "$vstics" == "v9" ]; then
    /opt/stics/bin/stics_modulo #> /dev/null
else
    /opt/sticsv10/bin/stics_modulo #> /dev/null
fi
base=$(basename "$USM_DIR")
if [ -f "mod_rapport.sti" ] && [ "$nbplt" -eq 1 ]; then
    mv mod_rapport.sti "$input_dir/mod_rapport_$base.sti"
fi
wait 
if [ -f "mod_rapportA.sti" ] && [ "$nbplt" -eq 2 ]; then
    mv mod_rapportA.sti "$input_dir/mod_rapport_${base}_A.sti"
fi
wait 
if [ -f "mod_rapportP.sti" ] && [ "$nbplt" -eq 2 ]; then
    mv mod_rapportP.sti "$input_dir/mod_rapport_${base}_P.sti"
fi
wait

if [ $dt -eq 1 ]; then
    rm -rf "$USM_DIR"
fi
cd "$OLD_PWD"

