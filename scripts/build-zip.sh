#!/usr/bin/env bash
# Build the Kodi addon zip ready for installation via "Install from zip"
# in Kodi 21 Omega (or for distribution through a Kodi addon repository).
#
# Usage:
#   scripts/build-zip.sh [--output DIR] [--ref REF]
#
# Defaults:
#   --output  ./dist
#   --ref     HEAD
#
# Output:
#   <output>/plugin.audio.squeezebox-<version>.zip
#
# The zip is built from git-tracked files at the given ref, so uncommitted
# changes are ignored — the script warns if the working tree is dirty.
# Test/doc/script files that are tracked but shouldn't ship are stripped.

set -euo pipefail

ADDON_ID="plugin.audio.squeezebox"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

output_dir="dist"
ref="HEAD"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output) output_dir="$2"; shift 2 ;;
        --ref)    ref="$2";        shift 2 ;;
        -h|--help)
            sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

# Extract version from addon.xml at the target ref (not from working tree)
version="$(git show "${ref}:addon.xml" \
    | python3 -c "import sys, xml.etree.ElementTree as ET; print(ET.fromstring(sys.stdin.read()).get('version'))")"

if [[ -z "$version" ]]; then
    echo "ERROR: could not extract version from addon.xml at ${ref}" >&2
    exit 1
fi

zip_name="${ADDON_ID}-${version}.zip"
zip_path="${output_dir}/${zip_name}"

# Warn if the working tree has uncommitted changes — they will NOT be in the zip
if ! git diff --quiet HEAD -- || ! git diff --cached --quiet --; then
    echo "WARNING: working tree has uncommitted changes; zip uses ${ref} only" >&2
fi

mkdir -p "$output_dir"

stage_dir="$(mktemp -d)"
trap 'rm -rf "$stage_dir"' EXIT

# Stage tracked files under the addon-id prefix Kodi expects
git archive --format=tar --prefix="${ADDON_ID}/" "$ref" | tar -x -C "$stage_dir"

# Strip dev-only files (tracked but shouldn't ship)
rm -rf "${stage_dir}/${ADDON_ID}/tests"
rm -rf "${stage_dir}/${ADDON_ID}/docs"
rm -rf "${stage_dir}/${ADDON_ID}/scripts"
rm -rf "${stage_dir}/${ADDON_ID}/repo"
rm -rf "${stage_dir}/${ADDON_ID}/.github"
rm -f  "${stage_dir}/${ADDON_ID}/pytest.ini"
rm -f  "${stage_dir}/${ADDON_ID}/requirements-dev.txt"
rm -f  "${stage_dir}/${ADDON_ID}/.gitignore"

# Sanity check
if [[ ! -f "${stage_dir}/${ADDON_ID}/addon.xml" ]]; then
    echo "ERROR: staging is malformed — addon.xml missing" >&2
    exit 1
fi
if [[ ! -f "${stage_dir}/${ADDON_ID}/service.py" ]] \
   || [[ ! -f "${stage_dir}/${ADDON_ID}/plugin.py" ]]; then
    echo "ERROR: staging is missing entry-point files" >&2
    exit 1
fi
if [[ ! -d "${stage_dir}/${ADDON_ID}/resources/lib" ]]; then
    echo "ERROR: staging is missing resources/lib" >&2
    exit 1
fi

# Build the zip from the staging dir
rm -f "$zip_path"
abs_zip_path="$(cd "$output_dir" && pwd -P)/${zip_name}"
(cd "$stage_dir" && zip -r9 -q "$abs_zip_path" "$ADDON_ID")

# Report
size="$(du -h "$zip_path" | cut -f1)"
file_count="$(unzip -Z1 "$zip_path" | wc -l)"
echo "Built ${zip_path} (${size}, ${file_count} files, version ${version})"
