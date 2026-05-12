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
