#!/usr/bin/env bash
cd "$(dirname "$0")"

APP="$PWD/osinaldi_bluray_multiburner.py"
LOG_DIR="$HOME/OsinaldiBurnLogs"
mkdir -p "$LOG_DIR"

# Launch detached from this terminal.
# This prevents closing the terminal from killing the GUI.
if command -v setsid >/dev/null 2>&1; then
    setsid /usr/bin/python3 "$APP" >> "$LOG_DIR/osinaldi_gui.log" 2>&1 < /dev/null &
else
    nohup /usr/bin/python3 "$APP" >> "$LOG_DIR/osinaldi_gui.log" 2>&1 < /dev/null &
fi

echo "Osinaldi BluRay MultiBurner started detached."
echo "You can close this terminal safely."
echo "GUI log: $LOG_DIR/osinaldi_gui.log"
