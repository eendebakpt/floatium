#!/usr/bin/env bash
# Sync vendored fast_float library headers under third_party/fast_float/
# from a local checkout of upstream
# (https://github.com/fastfloat/fast_float).
#
# Usage:   tools/sync_fast_float.sh [/path/to/fast_float]
# Default: ~/fast_float
#
# Idempotent. Overwrites the 9 vendored headers + LICENSE files in
# third_party/fast_float/ and rewrites README.vendor with the resolved
# upstream tag and commit. fast_float is header-only; the entire public
# include set is vendored.

set -euo pipefail

FF="${1:-$HOME/fast_float}"

if [[ ! -d "$FF/.git" ]]; then
    echo "error: $FF is not a git repo" >&2
    echo "       clone upstream fast_float first:" >&2
    echo "       git clone https://github.com/fastfloat/fast_float $FF" >&2
    exit 1
fi
if [[ ! -d "$FF/include/fast_float" ]]; then
    echo "error: $FF does not contain include/fast_float/ source directory" >&2
    exit 1
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
dest="$repo_root/third_party/fast_float"

echo "==> syncing vendored fast_float headers from $FF"

mkdir -p "$dest"

# The 9 public headers (fast_float is header-only; including
# fast_float.h transitively pulls in the rest).
files=(
    ascii_number.h
    bigint.h
    constexpr_feature_detect.h
    decimal_to_binary.h
    digit_comparison.h
    fast_float.h
    fast_table.h
    float_common.h
    parse_number.h
)

for f in "${files[@]}"; do
    src="$FF/include/fast_float/$f"
    if [[ ! -f "$src" ]]; then
        echo "error: $src not found" >&2
        exit 1
    fi
    cp "$src" "$dest/$f"
done

# Licenses (upstream is triple-licensed: Apache-2.0 OR MIT OR BSL-1.0).
for license in LICENSE-APACHE LICENSE-MIT LICENSE-BOOST; do
    if [[ -f "$FF/$license" ]]; then
        cp "$FF/$license" "$dest/$license"
    fi
done

# Record provenance.
commit="$(cd "$FF" && git rev-parse HEAD)"
short="$(cd "$FF" && git rev-parse --short HEAD)"
tag="$(cd "$FF" && git describe --tags --exact-match HEAD 2>/dev/null || echo '<no tag>')"
date_iso="$(cd "$FF" && git show -s --format=%cs HEAD)"

cat > "$dest/README.vendor" <<EOF
fast_float — Eisel-Lemire string-to-double parser
=================================================

Upstream:    https://github.com/fastfloat/fast_float
Tag:         $tag
Commit:      $short  ($date_iso)
License:     Apache-2.0 OR MIT OR BSL-1.0
             (see LICENSE-APACHE, LICENSE-MIT, LICENSE-BOOST)

Files vendored (all 9 upstream headers)
---------------------------------------
fast_float.h               — umbrella header, sole entry point for users
parse_number.h             — dispatch into the parser pipeline
float_common.h             — IEEE 754 bit layout, limits, adjusted_mantissa
ascii_number.h             — fast byte-level digit parsing
decimal_to_binary.h        — Clinger fast-path + Eisel-Lemire 64-bit path
digit_comparison.h         — big-int fallback for hard halfway cases
bigint.h                   — 4000-bit fixed-capacity bigint backing the
                             fallback
fast_table.h               — precomputed power-of-10 table
constexpr_feature_detect.h — compiler-probe macros

Algorithm
---------
Clinger's "small value" fast path → Eisel-Lemire 64-bit → if
indeterminate, digit-comparison bignum. This is the same two-phase
design used by Rust std, Go's strconv, DuckDB, Apache Arrow, folly,
etc.

Used by which backends
----------------------
fast_float — bridges floatium's parse path to fast_float::from_chars.

The bridge between fast_float and CPython's calling conventions is
src/cpython_adapter/fast_float_strtod.cc.

Build configuration
-------------------
    \$(CXX) -std=c++17 -fno-exceptions -fno-rtti

fast_float is header-only; the only .cc file in floatium's adapter
directory is the shim. No throw sites in the hot path when
-fno-exceptions is set — parse errors are returned via std::errc.

Local modifications
-------------------
None. The vendored files are byte-identical to upstream.

Resync: tools/sync_fast_float.sh
EOF

echo "==> done. Commit: $commit"
echo "==> review: git -C '$repo_root' diff --stat third_party/fast_float/"
