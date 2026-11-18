#!/bin/sh
# Removes Stellanova. Your programs, the course copy and Studia's settings stay.
place="$HOME/.local/share/stellanova"
rm -f "$HOME/.local/bin/stellanova" "$HOME/.local/share/applications/stellanova-studia.desktop"
# (the sandbox helper belongs to root, so it may need sudo)
rm -rf "$place" 2>/dev/null || sudo rm -rf "$place"
echo "Stellanova is uninstalled."
