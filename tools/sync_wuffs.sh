#!/usr/bin/env bash
# Sync vendored Wuffs single-header float parser into third_party/wuffs/.
#
# Usage:   tools/sync_wuffs.sh [/path/to/cpython0]
# Default: ~/cpython0
#
# Source of truth: the dtoa_wuff branch on github.com/eendebakpt/cpython,
# which ships Python/_ryu/floatconv_wuffs.h — a pre-extracted, single-
# header build of Wuffs' string-to-double subset (parse_number_f64,
# HPD, Eisel-Lemire). Floatium pulls from there rather than from upstream
# Wuffs directly because upstream Wuffs ships a multi-megabyte single-
# file release covering every supported codec, and the float-parsing
# extract requires a transpiler run that we don't want to repeat on
# every contributor machine.
#
# Re-pin: bump the source branch on ~/cpython0, re-run this script,
# review the diff, commit.

set -euo pipefail

CP="${1:-$HOME/cpython0}"
BRANCH="dtoa_wuff"

if [[ ! -d "$CP/.git" ]]; then
    echo "error: $CP is not a git repo" >&2
    exit 1
fi

if ! git -C "$CP" rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    echo "error: branch $BRANCH not found in $CP" >&2
    exit 1
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
dest="$repo_root/third_party/wuffs"
adapter="$repo_root/src/cpython_adapter"

echo "==> syncing vendored Wuffs subset from $CP@$BRANCH"

mkdir -p "$dest"

# Single-header float parser. No local mods at the include-path level
# (the header is self-contained).
git -C "$CP" show "$BRANCH:Python/_ryu/floatconv_wuffs.h" > "$dest/floatconv_wuffs.h"
git -C "$CP" show "$BRANCH:Python/_ryu/LICENSE-Wuffs"     > "$dest/LICENSE-Wuffs"

# Local fix (README.vendor, local modification 7; reported upstream):
# integer-part digits beyond the 800-digit HPD cap must still advance
# the decimal point. Fails loudly if the upstream hunk changed shape —
# check whether upstream fixed it and drop this step if so.
python3 - "$dest/floatconv_wuffs.h" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
s = p.read_text()
old = (
    "          dp = (int32_t)nd;\n"
    "        } else if ('0' != *p) {\n"
    "          // Long-tail non-zeroes set the truncated bit.\n"
    "          h->truncated = true;\n"
    "        }"
)
new = (
    "          dp = (int32_t)nd;\n"
    "        } else {\n"
    "          // floatium-local fix (see README.vendor, local modification 7):\n"
    "          // integer-part digits past the precision cap still shift the\n"
    "          // decimal point, otherwise \"1\" + 800 zeros parses as 1e799.\n"
    "          dp++;\n"
    "          if ('0' != *p) {\n"
    "            // Long-tail non-zeroes set the truncated bit.\n"
    "            h->truncated = true;\n"
    "          }\n"
    "        }"
)
if s.count(old) != 1:
    sys.exit("sync_wuffs: HPD integer-digit hunk not found exactly once; "
             "upstream may have changed (or fixed) it — review by hand")
s = s.replace(old, new)
# README.vendor item 8: MSVC cannot include <intrin.h> at block scope, so
# hoist the two in-function includes of the extract to the top.
infn = "#elif defined(_MSC_VER) && (defined(_M_X64) || defined(_M_ARM64))\n#include <intrin.h>\n"
if s.count(infn) != 2:
    sys.exit("sync_wuffs: expected two in-function <intrin.h> includes")
s = s.replace(infn, "#elif defined(_MSC_VER) && (defined(_M_X64) || defined(_M_ARM64))\n")
top = "#include <string.h>   /* memcpy */\n"
if s.count(top) != 1:
    sys.exit("sync_wuffs: include block not found")
s = s.replace(top, top + "#if defined(_MSC_VER) && (defined(_M_X64) || defined(_M_ARM64))\n"
    "#include <intrin.h>   /* _umul128, _BitScanReverse64 (floatium: hoisted out of\n"
    "                         the function bodies below; a system header included\n"
    "                         inside a function does not compile with MSVC) */\n#endif\n")
p.write_text(s)
PY

# Adapter (pystrtod_wuffs.h): apply the only local mod — rewrite
# `#include "_ryu/floatconv_wuffs.h"` → `#include "floatconv_wuffs.h"`
# so it resolves against floatium's flatter third_party/wuffs/ layout.
git -C "$CP" show "$BRANCH:Python/_ryu/pystrtod_wuffs.h" \
    | sed 's|#include "_ryu/floatconv_wuffs.h"|#include "floatconv_wuffs.h"|g' \
    | sed 's|_PyWuffs_strtod|_Py_wuffs_strtod_impl|g' \
    > "$adapter/pystrtod_wuffs.h"

commit="$(git -C "$CP" rev-parse "$BRANCH")"
date_iso="$(git -C "$CP" show -s --format=%cs "$BRANCH")"

echo "==> done. Source: $CP@$BRANCH ($commit, $date_iso)"
echo "==> review: git -C '$repo_root' diff --stat third_party/wuffs/ \\"
echo "                                  src/cpython_adapter/pystrtod_wuffs.h"
