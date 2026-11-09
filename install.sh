#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${CODEX_WEEKLY_RING_HOME:-$HOME/.local/share/codex-weekly-ring}"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
SYSTEMD_USER_DIR="$CONFIG_DIR/systemd/user"
AUTOSTART_DIR="$CONFIG_DIR/autostart"
UNIT_FILE="$SYSTEMD_USER_DIR/codex-weekly-ring.service"

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$SYSTEMD_USER_DIR" "$AUTOSTART_DIR"
install -m 0644 "$SOURCE_DIR/codex_weekly_ring.py" "$INSTALL_DIR/codex_weekly_ring.py"

cat > "$BIN_DIR/codex-weekly-ring" <<'WRAPPER'
#!/usr/bin/env bash
exec /usr/bin/python3 "$HOME/.local/share/codex-weekly-ring/codex_weekly_ring.py" "$@"
WRAPPER
if [[ "$INSTALL_DIR" != "$HOME/.local/share/codex-weekly-ring" ]]; then
  cat > "$BIN_DIR/codex-weekly-ring" <<WRAPPER
#!/usr/bin/env bash
exec /usr/bin/python3 "$INSTALL_DIR/codex_weekly_ring.py" "\$@"
WRAPPER
fi
chmod 0755 "$BIN_DIR/codex-weekly-ring"

cat > "$UNIT_FILE" <<UNIT
[Unit]
Description=Codex 7-day usage limit ring
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$BIN_DIR/codex-weekly-ring
Restart=on-failure
RestartSec=3
Environment=DISPLAY=${DISPLAY:-:0}
Environment=XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}
Environment=DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}

[Install]
WantedBy=graphical-session.target
UNIT

rm -f "$AUTOSTART_DIR/codex-weekly-ring.desktop"
systemctl --user daemon-reload
systemctl --user enable codex-weekly-ring.service >/dev/null
systemctl --user restart codex-weekly-ring.service
printf 'Installed and started the Codex weekly limit ring.\n'
