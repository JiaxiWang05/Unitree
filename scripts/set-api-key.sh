#!/usr/bin/env bash
# Store an API key on the Jetson without showing it on screen or in shell history.
# Run this yourself on the laptop (Claude should not handle the key):
#
#   scripts/set-api-key.sh unitree@<jetson-address>                  # OPENAI_API_KEY
#   scripts/set-api-key.sh unitree@<jetson-address> GEMINI_API_KEY   # optional Gemini backend
set -euo pipefail
HOST=${1:?usage: $0 user@jetson [OPENAI_API_KEY|GEMINI_API_KEY]}
NAME=${2:-OPENAI_API_KEY}
read -rsp "Paste ${NAME} (input hidden), then press Enter: " KEY
echo
[ -n "$KEY" ] || { echo "nothing entered"; exit 1; }
printf '%s\n' "$KEY" | ssh "$HOST" "cd ~/g1-greeter && python3 -m greeter.envfile --set ${NAME}"
ssh "$HOST" "systemctl --user restart g1-greeter 2>/dev/null || true"
