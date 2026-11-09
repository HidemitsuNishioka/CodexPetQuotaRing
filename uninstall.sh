#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${CODEX_WEEKLY_RING_HOME:-$HOME/.local/share/codex-weekly-ring}"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
AUTOSTART_DIR="$CONFIG_DIR/autostart"
UNIT_FILE="$CONFIG_DIR/systemd/user/codex-weekly-ring.service"

systemctl --user disable --now codex-weekly-ring.service >/dev/null 2>&1 || true
rm -f "$UNIT_FILE"
systemctl --user daemon-reload >/dev/null 2>&1 || true
rm -f "$HOME/.local/bin/codex-weekly-ring" "$AUTOSTART_DIR/codex-weekly-ring.desktop"
rm -rf "$INSTALL_DIR"
rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/codex-weekly-ring"
printf 'Removed the Codex weekly limit ring.\n'
