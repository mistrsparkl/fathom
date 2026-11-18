#!/bin/sh
# Installs Stellanova for this user. Run:
#   curl -fsSL https://raw.githubusercontent.com/mistrsparkl/stellanova/main/install.sh | sh
set -e
place="$HOME/.local/share/stellanova"
bin="$HOME/.local/bin"
url="${STELLANOVA_TAR:-https://github.com/mistrsparkl/stellanova/releases/latest/download/stellanova-linux.tar.gz}"

echo "Installing Stellanova..."

# Python runs it. clang and these headers make programs fast (without them they still run, just slower).
want="python3 clang libx11-dev libfreetype-dev libpng-dev libpulse-dev libgl-dev"
if command -v apt-get >/dev/null 2>&1; then
    need=""
    for p in $want; do dpkg -s "$p" >/dev/null 2>&1 || need="$need $p"; done
    if [ -n "$need" ]; then
        echo "Getting$need (sudo will ask for your password)..."
        sudo apt-get install -y $need || echo "Couldn't get them all. Stellanova still works, but programs run slower."
    fi
elif ! command -v python3 >/dev/null 2>&1; then
    echo "Stellanova needs Python 3. Install it with your package manager, then run this again."
    exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
echo "Downloading Stellanova..."
if [ -f "$url" ]; then cp "$url" "$work/s.tar.gz"; else curl -fsSL "$url" -o "$work/s.tar.gz"; fi
mkdir "$work/s"
tar -xzf "$work/s.tar.gz" -C "$work/s"
rm -rf "$place"
mkdir -p "$(dirname "$place")" "$bin"
mv "$work/s" "$place"
ln -sf "$place/stellanova" "$bin/stellanova"

# Chromium's sandbox needs this helper to belong to root. If that can't be done, Studia runs without it.
sandbox=""
if ! sudo -n true 2>/dev/null; then echo "Setting up Stellanova Studia (sudo may ask for your password again)..."; fi
if ! { sudo chown root:root "$place/studia-window/chrome-sandbox" && sudo chmod 4755 "$place/studia-window/chrome-sandbox"; }; then
    sandbox=" --no-sandbox"
fi

mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/stellanova-studia.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Stellanova Studia
Comment=Write and run Stellanova programs
Exec="$place/studia-window/electron"$sandbox "$place/editor/studia"
Path=$place/editor/studia
Terminal=false
Categories=Development;Education;
EOF

echo
echo "Stellanova is installed."
echo "  Open Stellanova Studia from your apps, and press Learn to start the course."
case ":$PATH:" in
    *":$bin:"*) echo "  Or in a terminal:  stellanova hello.stella" ;;
    *)
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
        echo "  Or in a new terminal (after logging in again):  stellanova hello.stella" ;;
esac
echo "  To remove it:  sh $place/uninstall.sh"
