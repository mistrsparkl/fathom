#!/bin/sh
# Removes Fathom. Your programs, the course copy and Studio's settings stay.
place="$HOME/.local/share/fathom"
rm -f "$HOME/.local/bin/fathom" "$HOME/.local/share/applications/fathom-studio.desktop"
[ -f /usr/share/applications/fathom-studio.desktop ] && sudo rm -f /usr/share/applications/fathom-studio.desktop
# (the sandbox helper belongs to root, so it may need sudo)
rm -rf "$place" 2>/dev/null || sudo rm -rf "$place"
echo "Fathom is uninstalled."
