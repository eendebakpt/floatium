#!/usr/bin/env bash
# Sync the vendored zmij C library into third_party/zmij/ from a local
# checkout of upstream (https://github.com/vitaut/zmij).
#
# Usage:   tools/sync_zmij.sh [/path/to/zmij]
# Default: ~/zmij
#
# Only the C port is vendored (zmij.c + zmij-c.h); the C++ headers are
# not needed. The checkout must be recent enough to carry the fixed /
# scientific precision writers in the C API (zmij_detail_write_fixed_big
# et al., upstream main since mid-2026) — older checkouts and the
# Ryu-backed `cpython` fork branch only expose the shortest writer and
# are rejected.

set -euo pipefail

ZMIJ="${1:-$HOME/zmij}"

if [[ ! -d "$ZMIJ/.git" ]]; then
    echo "error: $ZMIJ is not a git repo" >&2
    echo "       git clone https://github.com/vitaut/zmij $ZMIJ" >&2
    exit 1
fi
if ! grep -q "zmij_detail_write_fixed_big" "$ZMIJ/zmij-c.h"; then
    echo "error: $ZMIJ/zmij-c.h has no precision writers; checkout is too old" >&2
    echo "       (or on a branch without the C precision API)" >&2
    exit 1
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
dest="$repo_root/third_party/zmij"

echo "==> syncing vendored zmij from $ZMIJ"
mkdir -p "$dest"
cp "$ZMIJ/zmij.c" "$dest/zmij.c"
cp "$ZMIJ/zmij-c.h" "$dest/zmij-c.h"
cp "$ZMIJ/LICENSE" "$dest/LICENSE"

commit="$(cd "$ZMIJ" && git rev-parse HEAD)"
short="$(cd "$ZMIJ" && git rev-parse --short HEAD)"
tag="$(cd "$ZMIJ" && git describe --tags --exact-match HEAD 2>/dev/null || git -C "$ZMIJ" describe --tags --always)"
date_iso="$(cd "$ZMIJ" && git show -s --format=%cs HEAD)"

cat > "$dest/README.vendor" <<EOV
Żmij — fast floating-point-to-string conversion (C port)
=========================================================

Upstream:    https://github.com/vitaut/zmij
Version:     $tag
Commit:      $short  ($date_iso)
License:     MIT OR BSL-1.0 (see LICENSE)

Files vendored
--------------
zmij.c       — the complete C implementation: shortest round-trip
               (Schubfach-family algorithm, formally verified in Lean
               upstream), plus fixed / scientific / general precision
               writers with a bigint path for precisions above 18.
zmij-c.h     — public C API (zmij_write, zmij_write_fixed,
               zmij_write_scientific, ...).
LICENSE      — upstream license text.

The C++ headers (zmij.h, zmij.cc, zmij-to-chars.h) are deliberately not
vendored: the point of this backend is a pure-C float-formatting path
that could be proposed for CPython itself.

Used by which backends
----------------------
zmij — all three dtoa modes (0 shortest / 2 significant / 3 fixed,
       including negative ndigits) via src/cpython_adapter/zmij_dtoa.c,
       which is written as plain C against the _Py_dg_dtoa contract so
       it can move into Python/ next to pystrtod.c unchanged.

Build configuration
-------------------
    \$(CC) -std=c11   (static_assert, stdbool; __int128 or _umul128)

Local modifications
-------------------
None. The vendored files are byte-identical to upstream.

Upstream requests (not yet filed)
---------------------------------
1. \`asm\` -> \`__asm__\` in the ZMIJ_ASM macro (zmij.c). With \`-std=c11\`,
   which is what CPython compiles with, \`asm\` is not a keyword and the
   three ZMIJ_ASM sites fail to compile. floatium builds with gnu11, so
   it is unaffected; CPython would not be.
2. A to-decimal entry point in the C API: \`{sig, exp}\` for the shortest
   representation (the shape of zmij.c's internal to_decimal_result),
   so a dtoa-style caller can skip writing and re-reading the text.
   Optionally the same for fixed / scientific precision.
3. \`extern "C"\` guards in zmij-c.h for inclusion from C++ TUs.

Resync: tools/sync_zmij.sh
EOV
echo "==> done. Commit: $commit"
echo "==> review: git -C '$repo_root' diff --stat third_party/zmij/"
