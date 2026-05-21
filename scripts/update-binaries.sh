#!/usr/bin/env bash
# Refresh resources/lib/bin/ with the latest squeezelite builds from
# https://sourceforge.net/projects/lmsclients/files/squeezelite/
#
# Ralph Irving (the upstream maintainer) publishes builds on SourceForge;
# there are no GitHub Releases. The "interstitial" download page returns
# HTML with a signed mirror URL — this script follows it.
#
# Versions are pinned at the top. When a newer build appears on SF, bump
# the corresponding constant and re-run.
#
# Not covered:
# - **x86_64 Linux** — Ralph doesn't publish a precompiled x86_64 binary.
#   Most distros package squeezelite directly (apt install squeezelite,
#   pacman -S squeezelite, etc.) or ship it via LibreELEC's
#   virtual.multimedia-tools addon (the utils.py path already handles
#   that). The legacy 2017 binary at bin/linux/squeezelite-i64 stays.
# - **macOS** — no official precompiled binary. Compile from
#   https://github.com/ralph-irving/squeezelite or use
#   https://github.com/aubreyfalconer/install-squeezelite-osx.

set -euo pipefail

# --- Pinned upstream versions (bump as new SF releases appear) ---
ARMHF_VER=2.0.0.1563     # Pi 2/3/4/5 on 32-bit OS
AARCH64_VER=2.0.0.1541   # Pi 4/5 on 64-bit OS, LibreELEC 12 ARM, Jetson, etc.
WIN32_VER=2.0.0-1519
WIN64_VER=2.0.0-1524

SF_BASE="https://sourceforge.net/projects/lmsclients/files/squeezelite"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
bin_dir="resources/lib/bin"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Fetch an SF file via interstitial → meta refresh → signed mirror URL.
sf_fetch() {
    local path="$1"   # e.g. "linux/squeezelite-2.0.0.1541-aarch64.tar.gz"
    local out="$2"
    local interstitial="${work}/$(basename "$out").html"
    curl -sL -A "Mozilla/5.0" "${SF_BASE}/${path}/download" -o "$interstitial"
    local signed
    signed=$(python3 - "$interstitial" <<'PY'
import re, sys
html = open(sys.argv[1]).read()
m = re.search(r'<meta http-equiv="refresh" content="\d+; url=([^"]+)"', html)
if not m:
    sys.exit("No meta refresh URL found in interstitial")
print(m.group(1).replace("&amp;", "&"))
PY
)
    curl -sL -A "Mozilla/5.0" "$signed" -o "$out"
    if ! file "$out" | grep -qE "(gzip compressed|Zip archive)"; then
        echo "ERROR: $out doesn't look like a tarball/zip" >&2
        file "$out" >&2
        exit 1
    fi
}

# --- Linux: armhf (Pi 2/3, 32-bit Pi OS) ---
echo "==> Fetching Linux armhf $ARMHF_VER"
sf_fetch "linux/squeezelite-${ARMHF_VER}-armhf.tar.gz" "${work}/armhf.tar.gz"
tar -xzf "${work}/armhf.tar.gz" -C "${work}"
install -m 755 "${work}/squeezelite" "${bin_dir}/linux/squeezelite-arm"
install -m 644 "${work}/LICENSE.txt" "${bin_dir}/linux/LICENSE.txt"
rm "${work}/squeezelite" "${work}/LICENSE.txt"

# --- Linux: aarch64 (Pi 4/5 + 64-bit OS, ARM64 in general) ---
echo "==> Fetching Linux aarch64 $AARCH64_VER (NEW)"
sf_fetch "linux/squeezelite-${AARCH64_VER}-aarch64.tar.gz" "${work}/aarch64.tar.gz"
tar -xzf "${work}/aarch64.tar.gz" -C "${work}"
install -m 755 "${work}/squeezelite" "${bin_dir}/linux/squeezelite-aarch64"
rm "${work}/squeezelite" "${work}/LICENSE.txt"

# --- Windows 32-bit ---
echo "==> Fetching Windows 32-bit $WIN32_VER"
sf_fetch "windows/squeezelite-${WIN32_VER}-win32.zip" "${work}/win32.zip"
mkdir -p "${work}/win32_extract"
unzip -qo "${work}/win32.zip" -d "${work}/win32_extract"
install -m 755 "${work}/win32_extract/squeezelite-win.exe" "${bin_dir}/win32/squeezelite-win.exe"
install -m 644 "${work}/win32_extract/LICENSE.txt" "${bin_dir}/win32/LICENSE.txt"

# --- Windows 64-bit (new dir) ---
echo "==> Fetching Windows 64-bit $WIN64_VER (NEW)"
mkdir -p "${bin_dir}/win64"
sf_fetch "windows/squeezelite-${WIN64_VER}-win64.zip" "${work}/win64.zip"
mkdir -p "${work}/win64_extract"
unzip -qo "${work}/win64.zip" -d "${work}/win64_extract"
install -m 755 "${work}/win64_extract/squeezelite-x64.exe" "${bin_dir}/win64/squeezelite-x64.exe"
install -m 644 "${work}/win64_extract/LICENSE.txt" "${bin_dir}/win64/LICENSE.txt"

# --- Cleanup obsolete files ---
# The new SF Windows builds are statically linked — the standalone DLLs
# shipped with the 2017 build (FLAC, faad2, mad, mpg123, ogg, soxr,
# vorbis, vorbisfile, portaudio) are no longer needed.
echo "==> Removing obsolete Windows DLLs (new builds are statically linked)"
rm -f "${bin_dir}/win32/"*.dll

echo
echo "==> Done. Resulting binaries:"
for f in \
    "${bin_dir}/linux/squeezelite-arm" \
    "${bin_dir}/linux/squeezelite-aarch64" \
    "${bin_dir}/linux/squeezelite-i64" \
    "${bin_dir}/linux/squeezelite-i386" \
    "${bin_dir}/win32/squeezelite-win.exe" \
    "${bin_dir}/win64/squeezelite-x64.exe" \
    "${bin_dir}/osx/squeezelite"; do
    if [[ -f "$f" ]]; then
        size=$(du -h "$f" | cut -f1)
        printf "    %-8s %s\n" "$size" "$f"
    else
        printf "    MISSING  %s\n" "$f"
    fi
done
