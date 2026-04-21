#!/usr/bin/env bash
# Sync vendored fmt and fast_float trees, plus their CPython-side wrappers,
# from the companion fmt-fastfloat branch in the CPython working tree.
#
# Usage:   tools/sync_from_cpython.sh [/path/to/cpython]
# Default: ~/cpython
#
# Idempotent. Overwrites third_party/fmt, third_party/fast_float, and
# src/cpython_adapter/{fmt_dtoa.cc,fast_float_strtod.cc}. Run this from the
# repo root whenever the upstream CPython branch moves.

set -euo pipefail

CPYTHON="${1:-$HOME/cpython}"
BRANCH="fmt-fastfloat"

if [[ ! -d "$CPYTHON/.git" ]]; then
    echo "error: $CPYTHON is not a git repo" >&2
    exit 1
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$CPYTHON"

if ! git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    echo "error: branch $BRANCH not found in $CPYTHON" >&2
    exit 1
fi

echo "==> syncing vendored trees from $CPYTHON@$BRANCH"

# Extract the tree from the branch without checking it out (avoids disturbing
# whatever the user has in their working tree).
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git archive "$BRANCH" -- Python/_fmt Python/_fast_float \
    | tar -x -C "$tmp"

# Vendored library sources go into third_party/. Wrappers go into
# src/cpython_adapter/.
rm -rf "$repo_root/third_party/fmt" "$repo_root/third_party/fast_float"
mkdir -p "$repo_root/third_party/fmt" "$repo_root/third_party/fast_float"

# fmt: base.h format.h format-inl.h LICENSE README.vendor  (everything except the .cc wrapper)
cp "$tmp/Python/_fmt/base.h"          "$repo_root/third_party/fmt/"
cp "$tmp/Python/_fmt/format.h"        "$repo_root/third_party/fmt/"
cp "$tmp/Python/_fmt/format-inl.h"    "$repo_root/third_party/fmt/"
cp "$tmp/Python/_fmt/LICENSE"         "$repo_root/third_party/fmt/"
cp "$tmp/Python/_fmt/README.vendor"   "$repo_root/third_party/fmt/"

# fast_float: all 9 headers + LICENSEs
cp "$tmp/Python/_fast_float/"*.h           "$repo_root/third_party/fast_float/"
cp "$tmp/Python/_fast_float/LICENSE-"*     "$repo_root/third_party/fast_float/"
cp "$tmp/Python/_fast_float/README.vendor" "$repo_root/third_party/fast_float/"

# Wrappers (the adaptations that make output bit-identical to stock CPython):
# vendored verbatim.
mkdir -p "$repo_root/src/cpython_adapter"
cp "$tmp/Python/_fmt/fmt_dtoa.cc"              "$repo_root/src/cpython_adapter/"
cp "$tmp/Python/_fast_float/fast_float_strtod.cc" "$repo_root/src/cpython_adapter/"

# Record provenance.
commit="$(git rev-parse "$BRANCH")"
cat > "$repo_root/third_party/SYNC_STATE" <<EOF
Synced from: $CPYTHON
Branch:      $BRANCH
Commit:      $commit
Date:        $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

echo "==> done. Commit: $commit"
echo "==> review: git -C '$repo_root' diff --stat"
