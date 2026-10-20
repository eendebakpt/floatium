#!/usr/bin/env bash
# Sync the vendored ffc.h (C99 port of fast_float) into third_party/ffc/
# from a local checkout of upstream (https://github.com/kolemannix/ffc.h).
#
# Usage:   tools/sync_ffc.sh [/path/to/ffc.h-checkout]
# Default: ~/ffc.h
#
# Single header; the three license texts come along. Upstream tags
# releases as vYY.MM.NN — check out a tag before syncing.

set -euo pipefail

FFC="${1:-$HOME/ffc.h}"

if [[ ! -d "$FFC/.git" ]]; then
    echo "error: $FFC is not a git repo" >&2
    echo "       git clone https://github.com/kolemannix/ffc.h $FFC" >&2
    exit 1
fi
if ! grep -q "ffc_from_chars_double_options" "$FFC/ffc.h"; then
    echo "error: $FFC/ffc.h does not look like the amalgamated header" >&2
    exit 1
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
dest="$repo_root/third_party/ffc"

echo "==> syncing vendored ffc.h from $FFC"
mkdir -p "$dest"
cp "$FFC/ffc.h" "$dest/ffc.h"
for license in LICENSE-APACHE LICENSE-MIT LICENSE-BOOST; do
    [[ -f "$FFC/$license" ]] && cp "$FFC/$license" "$dest/$license"
done

commit="$(cd "$FFC" && git rev-parse HEAD)"
short="$(cd "$FFC" && git rev-parse --short HEAD)"
tag="$(cd "$FFC" && git describe --tags --exact-match HEAD 2>/dev/null || git -C "$FFC" describe --tags --always)"
date_iso="$(cd "$FFC" && git show -s --format=%cs HEAD)"
version="$(grep -E '^#define FFC_VERSION_(YEAR|MONTH|BUILD)' "$FFC/ffc.h" | awk '{printf "%s.", $3}' | sed 's/\.$//')"

cat > "$dest/README.vendor" <<EOV
ffc.h — C99 port of fast_float (string-to-double)
=================================================

Upstream:    https://github.com/kolemannix/ffc.h
Version:     $tag (FFC_VERSION $version)
Commit:      $short  ($date_iso)
License:     Apache-2.0 OR MIT OR BSL-1.0
             (see LICENSE-APACHE, LICENSE-MIT, LICENSE-BOOST)

Files vendored
--------------
ffc.h        — the amalgamated single header: Clinger fast path,
               Eisel-Lemire, and fast_float's digit-comparison bigint
               fallback, ported line by line from fast_float to C99.
               Define FFC_IMPL in exactly one C translation unit.

Why this and not fast_float / Wuffs
-----------------------------------
fast_float is C++, which CPython cannot vendor. Wuffs is C but its
float parser is an extract of a transpiler-generated multi-codec file,
rejects numbers with leading zeros ("0001.5"), and falls into a slow
high-precision-decimal path on 17-digit inputs (~12x slower than
ffc.h on floatium's random_bits corpus). ffc.h is a direct port of the
same algorithm fast_float uses, accepts the full strtod grammar, and
matched fast_float bit for bit on 5.3M published corpus lines plus
268k exact-midpoint / long-mantissa cases. It is used by valkey and
hiredis.

Used by which backends
----------------------
ffc — bridges floatium's parse path to ffc_from_chars_double_options
      via src/cpython_adapter/ffc_strtod.c (plain C, _Py_dg_strtod
      contract). Together with the zmij format backend this is the
      pure-C pair proposed for CPython.

Build configuration
-------------------
    \$(CC) -std=c11   (compiles cleanly under CPython's flags)

Local modifications
-------------------
None. The vendored files are byte-identical to upstream.

Resync: tools/sync_ffc.sh
EOV
echo "==> done. Commit: $commit"
