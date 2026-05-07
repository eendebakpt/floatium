#!/usr/bin/env bash
# Sync vendored Ryu library tree under third_party/ryu/ from a local
# checkout of upstream Ryu (https://github.com/ulfjack/ryu).
#
# Usage:   tools/sync_ryu.sh [/path/to/ryu]
# Default: ~/ryu
#
# Idempotent. Overwrites the 9 vendored files in third_party/ryu/ and
# rewrites README.vendor with the resolved upstream commit. Run this
# whenever floatium needs to re-pin to a newer Ryu commit.
#
# Note: the cpython_adapter glue (src/cpython_adapter/pystrtod_ryu.h)
# is *not* upstream Ryu — it lives in floatium and is not touched by
# this script. Companion ground-truth for the adapter is on the
# `rye_float` branch of github.com/eendebakpt/cpython, which is the
# reference for what the adapter must do.

set -euo pipefail

RYU="${1:-$HOME/ryu}"

if [[ ! -d "$RYU/.git" ]]; then
    echo "error: $RYU is not a git repo" >&2
    echo "       clone upstream Ryu first:" >&2
    echo "       git clone https://github.com/ulfjack/ryu $RYU" >&2
    exit 1
fi
if [[ ! -d "$RYU/ryu" ]]; then
    echo "error: $RYU does not contain ryu/ source directory" >&2
    exit 1
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
dest="$repo_root/third_party/ryu"

echo "==> syncing vendored Ryu tree from $RYU"

mkdir -p "$dest"

# The 9 source files we vendor (matches the set documented in
# third_party/ryu/README.vendor).
files=(
    ryu.h
    common.h
    digit_table.h
    d2s_intrinsics.h
    d2s.c
    d2s_full_table.h
    d2s_small_table.h
    d2fixed.c
    d2fixed_full_table.h
)

for f in "${files[@]}"; do
    src="$RYU/ryu/$f"
    if [[ ! -f "$src" ]]; then
        echo "error: $src not found" >&2
        exit 1
    fi
    # Apply the only local mod: rewrite `#include "ryu/X"` → `#include "X"`
    # so headers resolve when third_party/ryu/ is on the include path
    # (flattened directory, no nested ryu/).
    sed 's|#include "ryu/|#include "|g' "$src" > "$dest/$f"
done

# Licenses (upstream ships LICENSE-Apache2 and LICENSE-Boost; floatium's
# existing files are LICENSE-Apache and LICENSE-Boost — keep those names).
if [[ -f "$RYU/LICENSE-Apache2" ]]; then
    cp "$RYU/LICENSE-Apache2" "$dest/LICENSE-Apache"
fi
if [[ -f "$RYU/LICENSE-Boost" ]]; then
    cp "$RYU/LICENSE-Boost" "$dest/LICENSE-Boost"
fi

# Record provenance.
commit="$(cd "$RYU" && git rev-parse HEAD)"
date_iso="$(cd "$RYU" && git show -s --format=%cs HEAD)"

cat > "$dest/README.vendor" <<EOF
Ryu — Fast float-to-string conversion
=====================================

Upstream:  https://github.com/ulfjack/ryu
Author:    Ulf Adams
Commit:    $commit  ($date_iso)
License:   Apache License 2.0  (see LICENSE-Apache)
        OR Boost Software License 1.0  (see LICENSE-Boost)

Files vendored
--------------
ryu.h                Public API (d2s_buffered_n, d2fixed_buffered_n,
                     d2exp_buffered_n, ...)
common.h             Shared inline utilities (log2pow5, copy_special_str,
                     double_to_bits, ...)
digit_table.h        Two-digit lookup table used by digit output routines
d2s_intrinsics.h     Platform-specific 128-bit / intrinsic helpers
d2s.c                Shortest-representation conversion (mode 0 / repr)
d2s_full_table.h     Full lookup tables for d2s (DOUBLE_POW5_INV_SPLIT,
                     DOUBLE_POW5_SPLIT)
d2s_small_table.h    Smaller lookup tables (used when RYU_OPTIMIZE_SIZE
                     is defined)
d2fixed.c            Fixed-point and exponential conversion
                     (modes 2 and 3 / %f, %e, %g)
d2fixed_full_table.h Lookup tables for d2fixed / d2exp

Used by which backends
----------------------
fmt_opt    — d2fixed.c only (mode 3 / fixed precision)
ryu_opt    — d2s.c + d2fixed.c (modes 0 / 2 / 3) — pure-C alternative to
             fmt for callers who want zero C++ in the float-formatting
             path. Stock parse is recommended for full pure-C operation.

Local modifications
-------------------
d2s.c, d2fixed.c: changed \`#include "ryu/foo.h"\` to \`#include "foo.h"\` so
the headers resolve when \`third_party/ryu/\` is on the include path
(flattened directory, no nested ryu/).

No other modifications have been made to the upstream source.

Resync: tools/sync_ryu.sh
Licensing: Apache-2.0 OR Boost-1.0 (see LICENSE-Apache and LICENSE-Boost).
Both are compatible with floatium's MIT license.
EOF

echo "==> done. Commit: $commit"
echo "==> review: git -C '$repo_root' diff --stat third_party/ryu/"
