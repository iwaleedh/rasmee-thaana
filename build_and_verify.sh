#!/usr/bin/env bash
# THE release recipe: reproducible build of RasmeeThaana-Regular.ttf, digest check, then install.
# Pinned: release epoch 1795737600, version 1.007, hinting enabled. The build runs in a clean environment
# (env -i): only PATH, HOME and these settings reach it, so no exported override (NO_HINT, FONT_FAMILY, RASMEE_*, ...)
# can change a release build.
# The font is built into a temporary file and verified; only a matching file is moved to RasmeeThaana-Regular.ttf.
# Each failure is reported distinctly (BUILD FAILED / DIGEST MISMATCH / INSTALL FAILED); on any failure nothing is
# installed and any existing RasmeeThaana-Regular.ttf is left untouched.
set -uo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
if [ -d RasmeeThaana-Regular.ttf ]; then echo "INSTALL FAILED: RasmeeThaana-Regular.ttf is a directory" >&2; exit 1; fi
TMP="$(mktemp .RasmeeThaana-Regular.XXXXXX)" || { echo "BUILD FAILED: cannot create a temporary file" >&2; exit 1; }
trap 'rm -f "$TMP" "$TMP.ttf"' EXIT
env -i PATH="$PATH" HOME="$HOME" SOURCE_DATE_EPOCH=1795737600 FONT_VERSION=1.007 RASMEE_TEMP_BUILD=1 "$PY" tools/build.py --replace-approved "$TMP.ttf"   || { echo "BUILD FAILED: tools/build.py exited with an error; nothing installed" >&2; exit 1; }
"$PY" -c 'import hashlib,sys; d=hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest(); print("built    " + d); print("expected " + sys.argv[2]); sys.exit(0 if d==sys.argv[2] else 1)' "$TMP.ttf" a2ae5dec5ff661f22ad44bf9bd1a3c7a49119983e6c979a676d5ba712102240a   || { echo "DIGEST MISMATCH: the build does not match the approved release; nothing installed" >&2; exit 1; }
mv -f "$TMP.ttf" RasmeeThaana-Regular.ttf   || { echo "INSTALL FAILED: could not move the verified build to RasmeeThaana-Regular.ttf" >&2; exit 1; }
echo "digest matches the approved release; installed RasmeeThaana-Regular.ttf"
