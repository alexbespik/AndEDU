#!/usr/bin/env bash
# Stages what the desktop app bundles (electron-builder.yml extraResources):
#   build/desktop/backend/          tracked root *.py (not mcp_server.py), dist/, public/diagrams/, seed/topics/
#   build/desktop/python-<target>/  python-build-standalone + the locked wheels for that target
# Usage: scripts/desktop_stage.sh [mac-arm64|mac-x64|linux-x64|linux-arm64 ...]   (default: all four;
#        a bare arm64 or x64 means the mac build). Linux targets can be staged on a Mac.
# Only git-tracked files are copied: the live content/ folder holds personal courses and is never bundled.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/build/desktop"
CACHE="$ROOT/build/cache"
PY_TAG="20261026"
PY_VERSION="3.14.10"
# macOS ships bash 3.2 (no associative arrays): per-target values come from this function.
# check: mach:<lipo arch> for macOS, elf:<e_machine> for Linux (62 = x86-64, 183 = AArch64)
arch_info() {  # arch_info <target> triple|sha256|wheel (pip platform tags)|check
  case "$1:$2" in
    mac-arm64:triple)   echo aarch64-apple-darwin ;;
    mac-arm64:sha256)   echo 30a18bcb9ab75e485b4bf4e5d783dde165571e7e42c56dff47a2d2c5345183a4 ;;
    mac-arm64:wheel)    echo macosx_11_0_arm64 ;;
    mac-arm64:check)    echo mach:arm64 ;;
    mac-x64:triple)     echo x86_64-apple-darwin ;;
    mac-x64:sha256)     echo 01cedae5d4a66ac570e13cb35fa570d0e79ba8e9affd4518a5d85b6c2b98ff10 ;;
    mac-x64:wheel)      echo macosx_11_0_x86_64 ;;
    mac-x64:check)      echo mach:x86_64 ;;
    linux-x64:triple)   echo x86_64-unknown-linux-gnu ;;
    linux-x64:sha256)   echo 1b38024924eb7f4cf0cab45d7b871d1f1991354190fccd2625ac7529a43786e2 ;;
    linux-x64:wheel)    echo manylinux_2_28_x86_64 manylinux_2_17_x86_64 manylinux2014_x86_64 ;;
    linux-x64:check)    echo elf:62 ;;
    linux-arm64:triple) echo aarch64-unknown-linux-gnu ;;
    linux-arm64:sha256) echo dcc31ce7b9ddbbffac160da7fff0cc069054f43eca52382a7d0eebf94e985b88 ;;
    linux-arm64:wheel)  echo manylinux_2_28_aarch64 manylinux_2_17_aarch64 manylinux2014_aarch64 ;;
    linux-arm64:check)  echo elf:183 ;;
    *) echo "Unknown target: $1 (use mac-arm64, mac-x64, linux-x64 or linux-arm64)" >&2; exit 1 ;;
  esac
}
HOST_PYTHON="${HOST_PYTHON:-$ROOT/.venv/bin/python}"
TARGETS=""
for t in ${*:-mac-arm64 mac-x64 linux-x64 linux-arm64}; do
  case "$t" in arm64|x64) t="mac-$t" ;; esac
  arch_info "$t" triple >/dev/null   # rejects an unknown target before anything is built
  TARGETS="$TARGETS $t"
done

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
  local target="$1" triple
  triple="$(arch_info "$target" triple)"
  local archive="cpython-${PY_VERSION}+${PY_TAG}-${triple}-install_only.tar.gz"
  local dest="$OUT/python-$target"
  echo "== python $target"
  mkdir -p "$CACHE"
  if [ ! -f "$CACHE/$archive" ]; then
    curl -sSfL -o "$CACHE/$archive.part" \
      "https://github.com/astral-sh/python-build-standalone/releases/download/${PY_TAG}/${archive}"
    mv "$CACHE/$archive.part" "$CACHE/$archive"
  fi
  echo "$(arch_info "$target" sha256)  $CACHE/$archive" | shasum -a 256 -c -
  rm -rf "$dest" "$dest.unpack"
  mkdir -p "$dest.unpack"
  tar -xzf "$CACHE/$archive" -C "$dest.unpack"
  mv "$dest.unpack/python" "$dest" && rmdir "$dest.unpack"

  local site="$dest/lib/python3.14/site-packages" tag platforms=""
  # pip does not widen a manylinux_2_28 --platform to older tags (manylinux2014 = 2_17), so each is listed
  for tag in $(arch_info "$target" wheel); do platforms="$platforms --platform $tag"; done
  "$HOST_PYTHON" -m pip install --quiet --no-deps --require-hashes --only-binary=:all: \
    $platforms --python-version 3.14 --implementation cp \
    --target "$site" -r "$ROOT/desktop/requirements-$target.lock"

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
  local target="$1" check want f archs bad=0
  check="$(arch_info "$target" check)"
  want="${check#*:}"
  if [ "${check%%:*}" = elf ]; then
    check_elf "$target" "$want"
    return
  fi
  # every Mach-O file must contain the target arch (universal2 files carry both), and no ELF file may slip in
  while IFS= read -r -d '' f; do
    if [ "$(head -c 4 "$f" | od -An -tx1 | tr -d ' \n')" = 7f454c46 ]; then echo "   ELF file: $f"; bad=1; continue; fi
    archs="$(lipo -archs "$f" 2>/dev/null)" || continue   # not Mach-O
    case " $archs " in *" $want "*) ;; *) echo "   wrong arch ($archs): $f"; bad=1 ;; esac
  done < <(find "$OUT/python-$target" -type f \( -name '*.so' -o -name '*.dylib' -o -perm -u+x \) -print0)
  [ "$bad" = 0 ] || exit 1
  echo "   all Mach-O files in python-$target contain $want"
}

check_elf() {
  # every ELF file must be for the target machine, and no Mach-O file may slip in (a mac wheel by mistake)
  "$HOST_PYTHON" -I - "$OUT/python-$1" "$2" <<'PY'
import os, struct, sys
root, want = sys.argv[1], int(sys.argv[2])
macho = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe"}
bad = count = 0
for d, _, names in os.walk(root):
    for n in names:
        f = os.path.join(d, n)
        if os.path.islink(f) or not os.path.isfile(f):
            continue
        with open(f, "rb") as fh:
            head = fh.read(20)
        if head[:4] in macho:
            print(f"   Mach-O file: {f}"); bad = 1
        elif head[:4] == b"\x7fELF" and len(head) == 20:
            count += 1
            if head[5] != 1 or struct.unpack_from("<H", head, 18)[0] != want:
                print(f"   wrong machine: {f}"); bad = 1
if bad:
    sys.exit(1)
print(f"   all {count} ELF files in {os.path.basename(root)} are e_machine {want}, no Mach-O")
PY
}

stage_backend
compile_all "$OUT/backend"
for target in $TARGETS; do
  stage_python "$target"
  check_arch "$target"
  compile_all "$OUT/python-$target/lib/python3.14"
done
du -sh "$OUT"/* | sed 's/^/   /'
