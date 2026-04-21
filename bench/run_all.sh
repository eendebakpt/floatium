#!/usr/bin/env bash
# Run the full benchmark sweep. Writes per-bench JSON into bench/results/
# and prints an aggregated A/B table at the end.
#
# Usage:
#   bench/run_all.sh                   # default: fewer loops, ~1 min per bench
#   LOOPS=10 bench/run_all.sh          # more loops for publication-quality runs
set -euo pipefail

# Every bench installs/uninstalls floatium explicitly; if the .pth hook
# were also active, the two would fight. Unset for the whole sweep.
unset FLOATIUM_AUTOPATCH

cd "$(dirname "$0")/.."

mkdir -p bench/results
results="bench/results"
stamp=$(date -u +%Y%m%dT%H%M%SZ)

loops="${LOOPS:-3}"

benches=(bench_repr bench_format bench_parse bench_json)

for b in "${benches[@]}"; do
    out="${results}/${stamp}_${b}.json"
    echo "==> $b -> $out"
    python -m "bench.${b}" --loops="$loops" -o "$out"
done

# Aggregate into one file per stamp for easy diffing.
merged="${results}/${stamp}_merged.json"
python -m pyperf convert -o "$merged" "${results}/${stamp}_"*.json

echo
echo "==> Summary:"
python -m pyperf show "$merged" 2>/dev/null | tail -80

echo
echo "Wrote: ${results}/${stamp}_*.json"
echo "Compare A/B: python -m pyperf compare_to ${merged} ${merged}"
