#!/usr/bin/env bash
# Build the full Kodi repository structure for hosting on GitHub Pages.
#
# Output layout (under --output, default ./public):
#   public/
#   ├── addons.xml          (index of all addons)
#   ├── addons.xml.md5      (md5 of addons.xml)
#   ├── plugin.audio.squeezebox/
#   │   └── plugin.audio.squeezebox-<ver>.zip
#   └── repository.tom333-squeezebox/
#       └── repository.tom333-squeezebox-<ver>.zip
#
# Usage:
#   scripts/build-pages.sh [--output DIR] [--ref REF]

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

output_dir="public"
ref="HEAD"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output) output_dir="$2"; shift 2 ;;
        --ref)    ref="$2";        shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

rm -rf "$output_dir"
mkdir -p "$output_dir"

# --- 1. Build plugin.audio.squeezebox zip ---
plugin_version="$(git show "${ref}:addon.xml" \
    | python3 -c "import sys, xml.etree.ElementTree as ET; print(ET.fromstring(sys.stdin.read()).get('version'))")"
plugin_dir="${output_dir}/plugin.audio.squeezebox"
mkdir -p "$plugin_dir"

scripts/build-zip.sh --output "$plugin_dir" --ref "$ref"

# --- 2. Build the repository addon zip ---
# The repository addon lives at repo/repository.tom333-squeezebox/
# We package it directly without git archive since it has no dev artifacts.
repo_addon_id="repository.tom333-squeezebox"
repo_addon_src="repo/${repo_addon_id}"

if [[ ! -d "$repo_addon_src" ]]; then
    echo "ERROR: ${repo_addon_src} not found" >&2
    exit 1
fi

repo_version="$(python3 -c "import xml.etree.ElementTree as ET; print(ET.parse('${repo_addon_src}/addon.xml').getroot().get('version'))")"
repo_zip_dir="${output_dir}/${repo_addon_id}"
mkdir -p "$repo_zip_dir"

stage_dir="$(mktemp -d)"
trap 'rm -rf "$stage_dir"' EXIT
cp -r "$repo_addon_src" "${stage_dir}/${repo_addon_id}"
(cd "$stage_dir" && zip -r9 -q "$(pwd -P)/${repo_addon_id}-${repo_version}.zip" "$repo_addon_id")
mv "${stage_dir}/${repo_addon_id}-${repo_version}.zip" "${repo_zip_dir}/"

# --- 3. Generate addons.xml ---
# Kodi expects: <?xml version="1.0" encoding="UTF-8"?>\n<addons>...</addons>
# where each child is the full <addon> element from the addon's own addon.xml.

python3 - "$output_dir" "$plugin_version" "$repo_version" <<'PY'
import sys, xml.etree.ElementTree as ET
from pathlib import Path

output_dir, plugin_version, repo_version = sys.argv[1], sys.argv[2], sys.argv[3]
public = Path(output_dir)

def addon_from_zip(addon_id, version):
    """Re-read each addon's addon.xml from its source (working tree) so we
    don't have to unzip. The committed addon.xml is canonical."""
    if addon_id == "plugin.audio.squeezebox":
        path = Path("addon.xml")
    else:
        path = Path("repo") / addon_id / "addon.xml"
    return ET.parse(path).getroot()

addons_root = ET.Element("addons")
addons_root.append(addon_from_zip("plugin.audio.squeezebox", plugin_version))
addons_root.append(addon_from_zip("repository.tom333-squeezebox", repo_version))

# Pretty-print with declaration
ET.indent(addons_root, space="    ")
xml_bytes = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(addons_root, encoding="utf-8")
(public / "addons.xml").write_bytes(xml_bytes)
PY

# --- 4. Generate addons.xml.md5 ---
(cd "$output_dir" && md5sum addons.xml | awk '{print $1}' > addons.xml.md5)

# --- 5. Report ---
echo "Built Pages site in ${output_dir}/"
find "$output_dir" -type f | sort | sed "s|^${output_dir}/|  |"
echo
echo "Top-level URLs once deployed (assuming GitHub Pages on tom333/plugin.audio.squeezebox):"
echo "  https://tom333.github.io/plugin.audio.squeezebox/addons.xml"
echo "  https://tom333.github.io/plugin.audio.squeezebox/addons.xml.md5"
echo "  https://tom333.github.io/plugin.audio.squeezebox/plugin.audio.squeezebox/plugin.audio.squeezebox-${plugin_version}.zip"
echo "  https://tom333.github.io/plugin.audio.squeezebox/${repo_addon_id}/${repo_addon_id}-${repo_version}.zip"
