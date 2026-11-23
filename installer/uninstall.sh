#!/bin/sh
# Removes Fathom. Your programs, the course copy and Studia's settings stay.
place="$HOME/.local/share/fathom"
rm -f "$HOME/.local/bin/fathom" "$HOME/.local/share/applications/fathom-studia.desktop"
[ -f /usr/share/applications/fathom-studia.desktop ] && sudo rm -f /usr/share/applications/fathom-studia.desktop
# (the sandbox helper belongs to root, so it may need sudo)
rm -rf "$place" 2>/dev/null || sudo rm -rf "$place"
echo "Fathom is uninstalled."
