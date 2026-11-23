#!/bin/sh
# Installs Fathom for this user. Run:
#   curl -fsSL https://raw.githubusercontent.com/mistrsparkl/fathom/main/install.sh | sh
set -e
# (all in main, so a piped script is read in full before anything runs)
main() {
place="$HOME/.local/share/fathom"
bin="$HOME/.local/bin"
url="${FATHOM_TAR:-https://github.com/mistrsparkl/fathom/releases/latest/download/fathom-linux.tar.gz}"

echo "Installing Fathom..."

# Python runs it. clang and these headers make programs fast (without them they still run, just slower).
# libnss3 and ALSA are for Studia's window.
want="python3 clang libx11-dev libfreetype-dev libpng-dev libpulse-dev libgl-dev libnss3"
if command -v apt-get >/dev/null 2>&1; then
    if apt-cache show libasound2t64 >/dev/null 2>&1; then want="$want libasound2t64"; else want="$want libasound2"; fi
    need=""
    for p in $want; do dpkg -s "$p" >/dev/null 2>&1 || need="$need $p"; done
    if [ -n "$need" ]; then
        echo "Getting$need (sudo will ask for your password)..."
        sudo apt-get install -y $need < /dev/null || echo "Couldn't get them all. Fathom still works, but programs run slower."
    fi
elif ! command -v python3 >/dev/null 2>&1; then
    echo "Fathom needs Python 3. Install it with your package manager, then run this again."
    exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
echo "Downloading Fathom..."
if [ -f "$url" ]; then cp "$url" "$work/s.tar.gz"; else curl -fsSL "$url" -o "$work/s.tar.gz"; fi
mkdir "$work/s"
tar -xzf "$work/s.tar.gz" -C "$work/s"
rm -rf "$place"
mkdir -p "$(dirname "$place")" "$bin"
mv "$work/s" "$place"
ln -sf "$place/fathom" "$bin/fathom"

# Chromium's sandbox needs this helper to belong to root. If that can't be done, Studia runs without it.
sandbox=""
if ! sudo -n true 2>/dev/null; then echo "Setting up Fathom Studia (sudo may ask for your password again)..."; fi
if ! { sudo chown root:root "$place/studia-window/chrome-sandbox" && sudo chmod 4755 "$place/studia-window/chrome-sandbox"; }; then
    sandbox=" --no-sandbox"
fi

mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/fathom-studia.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Fathom Studia
Comment=Write and run Fathom programs
Exec="$place/studia-window/electron"$sandbox "$place/editor/studia"
Path=$place/editor/studia
Terminal=false
Categories=Development;Education;
EOF
# WSL's Start menu only lists apps from /usr/share/applications
if grep -qi microsoft /proc/version 2>/dev/null; then
    sudo cp "$HOME/.local/share/applications/fathom-studia.desktop" /usr/share/applications/ || true
fi

echo
echo "Fathom is installed."
echo "  Open Fathom Studia from your apps (on WSL: the Start menu, under Ubuntu), and press Learn to start the course."
case ":$PATH:" in
    *":$bin:"*) echo "  Or in a terminal:  fathom hello.fathom" ;;
    *)
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
        echo "  Or in a new terminal (after logging in again):  fathom hello.fathom" ;;
esac
echo "  To remove it:  sh $place/uninstall.sh"
}
main "$@"
