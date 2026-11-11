#!/usr/bin/env bash
# Stages what the desktop app bundles (electron-builder.yml extraResources):
#   build/desktop/backend/          tracked root *.py (not mcp_server.py), dist/, public/diagrams/, seed/topics/
#   build/desktop/python-<arch>/    python-build-standalone + the locked wheels for that arch
# Usage: scripts/desktop_stage.sh [arm64|x64 ...]   (default: both)
# Only git-tracked files are copied: the live content/ folder holds personal courses and is never bundled.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/build/desktop"
CACHE="$ROOT/build/cache"
PY_TAG="20261026"
PY_VERSION="3.14.10"
# macOS ships bash 3.2 (no associative arrays): per-arch values come from this function
arch_info() {  # arch_info <arch> triple|sha256|wheel|mach
  case "$1:$2" in
    arm64:triple) echo aarch64-apple-darwin ;;
    arm64:sha256) echo 30a18bcb9ab75e485b4bf4e5d783dde165571e7e42c56dff47a2d2c5345183a4 ;;
    arm64:wheel)  echo macosx_11_0_arm64 ;;
    arm64:mach)   echo arm64 ;;
    x64:triple)   echo x86_64-apple-darwin ;;
    x64:sha256)   echo 01cedae5d4a66ac570e13cb35fa570d0e79ba8e9affd4518a5d85b6c2b98ff10 ;;
    x64:wheel)    echo macosx_11_0_x86_64 ;;
    x64:mach)     echo x86_64 ;;
    *) echo "Unknown arch: $1 (use arm64 or x64)" >&2; exit 1 ;;
  esac
}
HOST_PYTHON="${HOST_PYTHON:-$ROOT/.venv/bin/python}"
ARCHES="${*:-arm64 x64}"

stage_backend() {
  echo "== frontend build"
  npm run build
  rm -rf "$OUT/backend"
  mkdir -p "$OUT/backend/public/diagrams" "$OUT/backend/seed/topics"
  git ls-files -z -- '*.py' ':!:*/*' ':!:mcp_server.py' | xargs -0 -I{} cp {} "$OUT/backend/"
  cp desktop_main.py "$OUT/backend/"   # the launcher, even before it is committed
  cp -R dist "$OUT/backend/dist"
  git ls-files -z -- 'public/diagrams' | xargs -0 -I{} cp {} "$OUT/backend/public/diagrams/"
  # library lessons as committed, not as edited on this machine
  git archive HEAD content/topics | tar -x -C "$OUT/backend/seed/topics" --strip-components=2
  echo "   $(ls "$OUT/backend" | wc -l | tr -d ' ') entries, $(ls "$OUT/backend/seed/topics" | wc -l | tr -d ' ') seed topics"
}

stage_python() {
  local arch="$1" triple
  triple="$(arch_info "$arch" triple)"
  local archive="cpython-${PY_VERSION}+${PY_TAG}-${triple}-install_only.tar.gz"
  local dest="$OUT/python-$arch"
  echo "== python $arch"
  mkdir -p "$CACHE"
  if [ ! -f "$CACHE/$archive" ]; then
    curl -sSfL -o "$CACHE/$archive.part" \
      "https://github.com/astral-sh/python-build-standalone/releases/download/${PY_TAG}/${archive}"
    mv "$CACHE/$archive.part" "$CACHE/$archive"
  fi
  echo "$(arch_info "$arch" sha256)  $CACHE/$archive" | shasum -a 256 -c -
  rm -rf "$dest" "$dest.unpack"
  mkdir -p "$dest.unpack"
  tar -xzf "$CACHE/$archive" -C "$dest.unpack"
  mv "$dest.unpack/python" "$dest" && rmdir "$dest.unpack"

  local site="$dest/lib/python3.14/site-packages"
  "$HOST_PYTHON" -m pip install --quiet --no-deps --require-hashes --only-binary=:all: \
    --platform "$(arch_info "$arch" wheel)" --python-version 3.14 --implementation cp \
    --target "$site" -r "$ROOT/desktop/requirements-$arch.lock"

  # not needed at run time; smaller bundle, fewer binaries to sign
  rm -rf "$dest/lib/python3.14/"{idlelib,tkinter,turtledemo,ensurepip,test} "$dest/lib/python3.14/lib-dynload/"_tkinter* \
    "$dest/lib/"{tcl,tk,itcl,thread}* "$dest/share" "$dest/include"
  rm -rf "$site/bin"
  find "$dest" -name 'tests' -path '*/site-packages/*' -type d -prune -exec rm -rf {} +
}

compile_all() {
  # bytecode is made now, before signing; the app runs with -B so nothing is written inside it later.
  # The host Python is 3.14 like the bundled one, so the bytecode format matches.
  "$HOST_PYTHON" -m compileall -q --invalidation-mode unchecked-hash "$@"
}

check_arch() {
  # every Mach-O file must contain the target arch (universal2 files carry both)
  local arch="$1" want f archs bad=0
  want="$(arch_info "$arch" mach)"
  while IFS= read -r -d '' f; do
    archs="$(lipo -archs "$f" 2>/dev/null)" || continue   # not Mach-O
    case " $archs " in *" $want "*) ;; *) echo "   wrong arch ($archs): $f"; bad=1 ;; esac
  done < <(find "$OUT/python-$arch" -type f \( -name '*.so' -o -name '*.dylib' -o -perm -u+x \) -print0)
  [ "$bad" = 0 ] || exit 1
  echo "   all Mach-O files in python-$arch contain $want"
}

stage_backend
compile_all "$OUT/backend"
for arch in $ARCHES; do
  stage_python "$arch"
  check_arch "$arch"
  compile_all "$OUT/python-$arch/lib/python3.14"
done
du -sh "$OUT"/* | sed 's/^/   /'
