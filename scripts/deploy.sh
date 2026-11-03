#!/usr/bin/env bash
# Copy this repository to the Jetson and (re)install it. Safe to repeat.
#
#   scripts/deploy.sh unitree@<jetson-address> [install.sh options, e.g. --with-local]
#
# Needs passwordless SSH (ssh-copy-id) and tar; nothing else on either side.
set -euo pipefail
HOST=${1:?usage: $0 user@jetson [--with-local] [--with-gemini] [--no-tensorrt] [--no-service]}
shift
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COPYFILE_DISABLE=1 # macOS tar: no ._ resource-fork files
tar -C "$HERE" -czf - \
  --exclude .git --exclude .venv --exclude __pycache__ --exclude .pytest_cache \
  --exclude ./models --exclude ./recordings --exclude ./hardware --exclude '*.pt' --exclude '*.engine' --exclude '*.onnx' --exclude '*.avi' \
  . | ssh "$HOST" 'mkdir -p ~/g1-greeter && cd ~/g1-greeter && rm -rf greeter scripts tests requirements \
        && tar --warning=no-unknown-keyword -xzf -'
ssh "$HOST" "bash ~/g1-greeter/scripts/install.sh $*"
