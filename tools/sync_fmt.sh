#!/usr/bin/env bash
# Sync vendored {fmt} library subset under third_party/fmt/ from a local
# checkout of upstream fmtlib (https://github.com/fmtlib/fmt).
#
# Usage:   tools/sync_fmt.sh [/path/to/fmt]
# Default: ~/fmt
#
# Idempotent. Overwrites the 3 vendored headers + LICENSE in
# third_party/fmt/ and rewrites README.vendor with the resolved upstream
# tag and commit. Run this whenever floatium needs to re-pin fmt.
#
# Floatium vendors only the headers reachable from the float-formatting
# path: format.h, format-inl.h, base.h. The other umbrella headers
# (chrono.h, color.h, compile.h, core.h, os.h, ostream.h, printf.h,
# ranges.h, std.h, xchar.h, args.h) are deliberately excluded — they
# would drag in locale/iostream/chrono dependencies that the float path
# does not need.

set -euo pipefail

FMT="${1:-$HOME/fmt}"

if [[ ! -d "$FMT/.git" ]]; then
    echo "error: $FMT is not a git repo" >&2
    echo "       clone upstream fmt first:" >&2
    echo "       git clone https://github.com/fmtlib/fmt $FMT" >&2
    exit 1
fi
if [[ ! -d "$FMT/include/fmt" ]]; then
    echo "error: $FMT does not contain include/fmt/ source directory" >&2
    exit 1
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
dest="$repo_root/third_party/fmt"

echo "==> syncing vendored fmt subset from $FMT"

mkdir -p "$dest"

# The 3 headers reachable from the float path.
files=(
    base.h
    format.h
    format-inl.h
)

for f in "${files[@]}"; do
    src="$FMT/include/fmt/$f"
    if [[ ! -f "$src" ]]; then
        echo "error: $src not found" >&2
        exit 1
    fi
    cp "$src" "$dest/$f"
done

# License (upstream ships a single LICENSE file).
if [[ -f "$FMT/LICENSE" ]]; then
    cp "$FMT/LICENSE" "$dest/LICENSE"
fi

# Record provenance.
commit="$(cd "$FMT" && git rev-parse HEAD)"
short="$(cd "$FMT" && git rev-parse --short HEAD)"
tag="$(cd "$FMT" && git describe --tags --exact-match HEAD 2>/dev/null || echo '<no tag>')"
date_iso="$(cd "$FMT" && git show -s --format=%cs HEAD)"

cat > "$dest/README.vendor" <<EOF
{fmt} — formatting library for C++
==================================

Upstream:    https://github.com/fmtlib/fmt
Tag:         $tag
Commit:      $short  ($date_iso)
License:     MIT (see LICENSE in this directory)

Files vendored
--------------
format.h        — core float formatting path, Dragon4 bignum, Dragonbox
                  shortest entry point declaration
format-inl.h    — out-of-line Dragonbox tables and helpers; #include'd
                  exactly once from src/cpython_adapter/fmt_dtoa.cc
base.h          — buffer, basic_fp, and utility types that format.h
                  depends on
LICENSE         — upstream MIT license text

Deliberately excluded: chrono.h, color.h, compile.h, core.h, os.h,
ostream.h, printf.h, ranges.h, std.h, xchar.h, args.h. None of these are
reachable from the float path; keeping them out of the tree avoids
dragging locale/iostream/chrono dependencies into the wheel.

Used by which backends
----------------------
fmt        — full Dragonbox + format_float path (modes 0/2/3)
fmt_opt    — Dragonbox shortest (mode 0) + fmt::detail::format_float
             scientific (mode 2); fixed-mode (mode 3) routes through
             Ryu d2fixed instead

The bridge between fmt and CPython's calling conventions is
src/cpython_adapter/fmt_dtoa.cc and src/cpython_adapter/fmt_opt_dtoa.cc.

Build configuration
-------------------
    \$(CXX) -std=c++17 -fno-exceptions -fno-rtti

fmt auto-detects -fno-exceptions via __cpp_exceptions and replaces its
throw sites with assertion failures. No RTTI is required on the float
path.

Local modifications
-------------------
None. The vendored files are byte-identical to upstream.

Resync: tools/sync_fmt.sh
EOF

echo "==> done. Commit: $commit"
echo "==> review: git -C '$repo_root' diff --stat third_party/fmt/"
