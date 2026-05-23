#!/usr/bin/env bash
set -e

echo "Installing dependencies for Osinaldi BluRay MultiBurner for Linux 1.0.0..."
echo

sudo apt update
sudo apt install -y python3 python3-pip python3-tk dvd+rw-tools util-linux eject zenity

echo
echo "Note:"
echo "The package is called dvd+rw-tools for historical Linux reasons,"
echo "but it contains growisofs, which can burn Blu-ray BD-R media."
echo

echo "Detecting system Python..."
PY_VERSION="$(/usr/bin/python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
TK_PACKAGE="python${PY_VERSION}-tk"

echo "Detected Python: $PY_VERSION"
echo "Specific Tkinter package: $TK_PACKAGE"

if apt-cache show "$TK_PACKAGE" >/dev/null 2>&1; then
    sudo apt install -y "$TK_PACKAGE"
fi

echo
echo "Checking Tkinter..."
/usr/bin/python3 - <<'PY'
import tkinter
print("Tkinter OK:", tkinter.TkVersion)
PY

echo
echo "Checking zenity..."
command -v zenity >/dev/null
echo "zenity OK. The native Linux file picker can show mounted drives."

echo
echo "Checking growisofs for Blu-ray burning..."
command -v growisofs >/dev/null
echo "growisofs OK."

echo
echo "Recommended permissions for daily use:"
echo "sudo usermod -aG cdrom \"$USER\""
echo "Then log out and log back in."
echo

echo "Done."
echo "Run:"
echo "./run.sh"
