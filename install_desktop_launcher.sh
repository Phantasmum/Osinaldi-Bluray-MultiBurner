#!/usr/bin/env bash
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_DIR/osinaldi-bluray-multiburner.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Osinaldi BluRay MultiBurner
Comment=Burn BD-R ISOs to multiple Blu-ray writers
Exec=$APP_DIR/run.sh
Icon=media-optical
Terminal=false
Categories=Utility;AudioVideo;
EOF

chmod +x "$DESKTOP_DIR/osinaldi-bluray-multiburner.desktop"

echo "Launcher installed:"
echo "$DESKTOP_DIR/osinaldi-bluray-multiburner.desktop"
echo
echo "You can now search for: Osinaldi BluRay MultiBurner"
