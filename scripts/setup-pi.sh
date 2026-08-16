#!/usr/bin/env bash
# One-shot (and re-runnable) setup for running song_to_movie as a systemd
# service: installs system + python deps, clones/updates the repo, and
# installs a service (auto-restart on crash) plus a timer that polls
# origin/main every few minutes and restarts the service when it changes.
#
# Usage (public repo, no credentials needed):
#   curl -fsSL https://raw.githubusercontent.com/oliverinhalo/song-to-movie-clips/main/scripts/setup-pi.sh | bash
set -euo pipefail

REPO_URL="https://github.com/oliverinhalo/song-to-movie-clips.git"
REPO_DIR="$HOME/song-to-movie-clips"
RUNS_DIR="$HOME/song-to-movie-runs"
SERVICE_USER="$USER"

echo "==> installing system packages"
sudo apt update
# rustc/cargo: some of the audio ML stack's dependencies (e.g. sphn) ship
# as Rust extensions with no prebuilt wheel for every Pi/Python
# combination, so pip falls back to compiling them via maturin - which
# needs a Rust toolchain present to succeed. cmake/build-essential/
# pkg-config: that same build compiles a bundled C library from source,
# which needs an actual C toolchain and cmake binary on PATH, not just
# cargo.
sudo apt install -y ffmpeg python3-venv python3-pip git rustc cargo cmake build-essential pkg-config

echo "==> fetching song_to_movie"
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull --ff-only origin main
else
  git clone "$REPO_URL" "$REPO_DIR"
fi

echo "==> python environment (this can take a while on a Pi - torch/demucs, plus compiling any Rust extensions from source)"
# If this step gets killed with no clear error on a low-RAM Pi (1-2GB),
# that's usually the Rust compiler running out of memory - add swap first:
#   sudo dphys-swapfile swapoff && sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile && sudo dphys-swapfile setup && sudo dphys-swapfile swapon
cd "$REPO_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[alignment,separation]"
deactivate

mkdir -p "$RUNS_DIR"

echo "==> installing song-to-movie.service"
sudo tee /etc/systemd/system/song-to-movie.service > /dev/null <<EOF
[Unit]
Description=song_to_movie web app
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$REPO_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$REPO_DIR/.venv/bin/python -m song_to_movie.webapp $RUNS_DIR --host 0.0.0.0 --port 5000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "==> granting a narrowly-scoped passwordless restart for the updater"
echo "$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart song-to-movie.service" \
  | sudo tee /etc/sudoers.d/song-to-movie > /dev/null
sudo chmod 0440 /etc/sudoers.d/song-to-movie
sudo visudo -c

echo "==> installing the update script"
mkdir -p "$REPO_DIR/scripts"
cat > "$REPO_DIR/scripts/update.sh" <<'SCRIPT_EOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

git fetch --quiet origin main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

echo "$(date -Is) updating $LOCAL -> $REMOTE"
git pull --ff-only origin main
source .venv/bin/activate
pip install -q -e ".[alignment,separation]"
sudo /usr/bin/systemctl restart song-to-movie.service
SCRIPT_EOF
chmod +x "$REPO_DIR/scripts/update.sh"

echo "==> installing the update timer"
sudo tee /etc/systemd/system/song-to-movie-update.service > /dev/null <<EOF
[Unit]
Description=Check song-to-movie-clips for updates and restart if changed

[Service]
Type=oneshot
User=$SERVICE_USER
ExecStart=$REPO_DIR/scripts/update.sh
EOF

sudo tee /etc/systemd/system/song-to-movie-update.timer > /dev/null <<'EOF'
[Unit]
Description=Periodically check song-to-movie-clips for updates

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "==> enabling everything"
sudo systemctl daemon-reload
sudo systemctl enable --now song-to-movie.service
sudo systemctl enable --now song-to-movie-update.timer

echo
echo "Done. Useful commands:"
echo "  systemctl status song-to-movie.service --no-pager"
echo "  journalctl -u song-to-movie.service -f"
echo "  systemctl list-timers song-to-movie-update.timer"
