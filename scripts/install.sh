#!/usr/bin/env bash
# Install or update the greeter on the G1's Jetson (PC2). No sudo; safe to re-run.
# Normally started by scripts/deploy.sh from the laptop. Run setup-jetson.sh (sudo, once) first.
#
#   bash ~/g1-greeter/scripts/install.sh [--with-local] [--with-gemini] [--no-tensorrt] [--no-service]
#
#   --with-local   offline fallback: Ollama (qwen3-vl:2b-instruct), Whisper, Kokoro, Silero (Python 3.10+)
#   --with-gemini  the Gemini Live backend (google-genai needs Python 3.10+)
#   --no-tensorrt  skip the TensorRT FP16 export of YOLO (built by default when CUDA works; ~5 min once)
#   --no-service   don't install/start the systemd user service
set -euo pipefail
APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF="$HOME/.config/g1-greeter"
ENVF="$CONF/greeter.env"
CYC="$HOME/cyclonedds/install"
UNIT_DIR="$HOME/.config/systemd/user"
export PATH="$HOME/.local/bin:$PATH"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
WITH_LOCAL=0 WITH_GEMINI=0 TENSORRT=1 SERVICE=1
for a in "$@"; do
  case "$a" in
    --with-local) WITH_LOCAL=1 ;; --with-gemini) WITH_GEMINI=1 ;;
    --no-tensorrt) TENSORRT=0 ;; --tensorrt) TENSORRT=1 ;; --no-service) SERVICE=0 ;;
    *) echo "unknown option: $a"; exit 2 ;;
  esac
done
step() { printf '\n== %s\n' "$*"; }
TODO=()
cd "$APP"

step "system"
L4T=$(sed -n 's/^# R\([0-9]*\).*/\1/p' /etc/nv_tegra_release 2>/dev/null | head -1)
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
echo "$(uname -m), L4T R${L4T:-?} (JetPack ${L4T:+$((L4T - 30))}), Python $(python3 --version | cut -d' ' -f2)"
missing=()
for c in git cmake make gcc g++ curl; do command -v "$c" >/dev/null || missing+=("$c"); done
if [ ${#missing[@]} -gt 0 ]; then
  echo "missing ${missing[*]}: the human needs to run scripts/setup-jetson.sh first (README: What the human does)"
  exit 3
fi
id -nG | grep -qw video || TODO+=("$USER is not in the video group yet: reboot once after setup-jetson.sh")

step "uv (Python package manager)"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version

step "virtual environment (system Python, so JetPack's CUDA/OpenCV stay usable)"
[ -x "$APP/.venv/bin/python" ] || uv venv --system-site-packages --python "$(command -v python3)" "$APP/.venv"
PY="$APP/.venv/bin/python"
pipi() { uv pip install --python "$PY" "$@"; }
NUMPY="numpy<2"
[ "$PYV" -lt 39 ] && NUMPY="numpy<1.25"

step "PyTorch"
EXTRA_LD=""
cuda_ok() { LD_LIBRARY_PATH="${EXTRA_LD}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" "$PY" -c 'import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)' 2>/dev/null; }
CSL="$HOME/.local/cusparselt"
[ -d "$CSL/lib" ] && EXTRA_LD="$CSL/lib"
CPU_TORCH=0
if cuda_ok; then
  echo "CUDA torch already available"
else
  UA=https://github.com/ultralytics/assets/releases/download/v0.0.0
  case "${L4T:-none}-$PYV" in
    35-38) # JetPack 5 (the wheels from the Ultralytics Jetson guide)
      pipi "$NUMPY" "$UA/torch-2.2.0-cp38-cp38-linux_aarch64.whl" "$UA/torchvision-0.17.2+c1d70fe-cp38-cp38-linux_aarch64.whl" || true ;;
    36-310) # JetPack 6: torch 2.5 also needs cuSPARSELt, installed here without sudo
      if [ ! -d "$CSL/lib" ]; then
        mkdir -p "$CSL"
        curl -fL https://developer.download.nvidia.com/compute/cusparselt/redist/libcusparse_lt/linux-aarch64/libcusparse_lt-linux-aarch64-0.7.1.0-archive.tar.xz |
          tar -xJ -C "$CSL" --strip-components=1
      fi
      EXTRA_LD="$CSL/lib"
      pipi "$NUMPY" "$UA/torch-2.5.0a0+872d972e41.nv24.08-cp310-cp310-linux_aarch64.whl" "$UA/torchvision-0.20.0a0+afc54f7-cp310-cp310-linux_aarch64.whl" || true ;;
  esac
  if ! cuda_ok; then
    echo "no CUDA torch for this JetPack/Python: falling back to CPU torch (YOLO at 416 px)"
    pipi --extra-index-url https://download.pytorch.org/whl/cpu "$NUMPY" torch torchvision
    CPU_TORCH=1
  fi
fi
# From here on no dependency may swap the torch set up above (e.g. NVIDIA's build for a PyPI one).
PINS="$APP/.venv/torch-pins.txt"
LD_LIBRARY_PATH="$EXTRA_LD" "$PY" -c 'import importlib
for n in ("torch", "torchvision"):
    try:
        print("%s==%s" % (n, importlib.import_module(n).__version__))
    except Exception:
        pass' >"$PINS"
echo "pinned: $(tr '\n' ' ' <"$PINS")"
pinned() { uv pip install --python "$PY" -c "$PINS" "$@"; }

step "Python packages"
"$PY" -c 'import cv2' 2>/dev/null || pinned "$NUMPY" "opencv-python>=4.7"
pinned "$NUMPY" "websockets>=13.1" "lap>=0.5.12" ultralytics-thop matplotlib pillow pyyaml requests scipy psutil polars
pinned --no-deps "ultralytics>=8.4.0" # its other dependencies are listed above
# head D435i depth for the talk spot (2.55.1 is the last release with a Python 3.8 aarch64 wheel)
if [ "$PYV" -lt 39 ]; then RS="pyrealsense2==2.55.1.6486"; else RS="pyrealsense2"; fi
pinned "$RS" || TODO+=("pyrealsense2 not installed: the talk spot falls back to the webcam estimate")
[ -f /etc/udev/rules.d/99-realsense-libusb.rules ] ||
  TODO+=("RealSense udev rules missing: the human re-runs scripts/setup-jetson.sh (sudo) so the greeter can open the head D435i")

step "Unitree SDK (unitree_sdk2_python + CycloneDDS 0.10)"
if "$PY" -c 'import unitree_sdk2py' 2>/dev/null; then
  echo "already installed"
else
  if [ ! -e "$CYC/lib/libddsc.so" ]; then
    rm -rf "$HOME/cyclonedds/src" "$HOME/cyclonedds/build"
    git clone --depth 1 -b releases/0.10.x https://github.com/eclipse-cyclonedds/cyclonedds "$HOME/cyclonedds/src"
    cmake -S "$HOME/cyclonedds/src" -B "$HOME/cyclonedds/build" -DCMAKE_INSTALL_PREFIX="$CYC" -DBUILD_EXAMPLES=OFF -DBUILD_TESTING=OFF
    cmake --build "$HOME/cyclonedds/build" --target install -j"$(nproc)"
  fi
  [ -d "$HOME/unitree_sdk2_python/.git" ] || git clone --depth 1 https://github.com/unitreerobotics/unitree_sdk2_python "$HOME/unitree_sdk2_python"
  CYCLONEDDS_HOME="$CYC" pinned -e "$HOME/unitree_sdk2_python"
fi
[ -d "$CYC/lib" ] && EXTRA_LD="${EXTRA_LD:+$EXTRA_LD:}$CYC/lib"

if [ "$WITH_GEMINI" = 1 ]; then
  step "Gemini backend"
  if [ "$PYV" -ge 310 ]; then pinned "google-genai>=2.31"; else
    TODO+=("Gemini skipped: google-genai needs Python 3.10+ (this Jetson has 3.${PYV#3}); OpenAI is the default anyway")
  fi
fi

step "models"
mkdir -p "$APP/models"
[ -s "$APP/models/yolo26n-pose.pt" ] || curl -fL --retry 3 -o "$APP/models/yolo26n-pose.pt" \
  https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-pose.pt
YOLO_MODEL="$APP/models/yolo26n-pose.pt"
if [ "$TENSORRT" = 1 ] && cuda_ok; then
  [ -s "$APP/models/yolo26n-pose.engine" ] || (cd "$APP/models" && LD_LIBRARY_PATH="$EXTRA_LD" "$PY" -c \
    "from ultralytics import YOLO; YOLO('yolo26n-pose.pt').export(format='engine', half=True, imgsz=640)")
  [ -s "$APP/models/yolo26n-pose.engine" ] && YOLO_MODEL="$APP/models/yolo26n-pose.engine"
fi

if [ "$WITH_LOCAL" = 1 ]; then
  step "offline fallback (--local)"
  if [ "$PYV" -lt 310 ]; then
    TODO+=("--with-local skipped: Kokoro/faster-whisper need Python 3.10+ (JetPack 6). Offline option on JetPack 5: run the laptop split with --local (README)")
  else
    OL="$HOME/.local/ollama"
    if [ ! -x "$OL/bin/ollama" ]; then
      mkdir -p "$OL"
      curl -fL https://ollama.com/download/ollama-linux-arm64.tar.zst | zstd -d | tar -x -C "$OL"
      case "${L4T:-}" in
        36) curl -fL https://ollama.com/download/ollama-linux-arm64-jetpack6.tar.zst | zstd -d | tar -x -C "$OL" ;;
        35) curl -fL https://ollama.com/download/ollama-linux-arm64-jetpack5.tar.zst | zstd -d | tar -x -C "$OL" ;;
      esac
    fi
    mkdir -p "$UNIT_DIR"
    cat >"$UNIT_DIR/ollama.service" <<EOF
[Unit]
Description=Ollama (user, for the greeter's offline fallback)

[Service]
Environment=OLLAMA_HOST=127.0.0.1:11434
ExecStart=$OL/bin/ollama serve
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now ollama
    for _ in $(seq 1 30); do curl -s -o /dev/null http://127.0.0.1:11434/api/tags && break; sleep 1; done
    "$OL/bin/ollama" pull qwen3-vl:2b-instruct
    pinned "faster-whisper>=1.2" "ollama>=0.6" "kokoro>=0.9.4"
    pinned --no-deps "silero-vad>=6.0" # its torchaudio dependency would pin another torch; not needed here
    # fetch the speech models now so the fallback works without internet
    LD_LIBRARY_PATH="$EXTRA_LD" "$PY" - <<'EOF'
from silero_vad import load_silero_vad
from faster_whisper import WhisperModel
from kokoro import KPipeline
load_silero_vad()
WhisperModel("base.en", device="cpu", compute_type="int8")
list(KPipeline(lang_code="b")("Hello.", voice="bf_emma"))
print("offline speech models cached")
EOF
  fi
fi

step "settings ($ENVF)"
mkdir -p "$CONF" && chmod 700 "$CONF"
if [ ! -f "$ENVF" ]; then
  (umask 077 && cat >"$ENVF" <<'EOF'
# g1-greeter settings. KEY=value, one per line. Read by the service and by `python -m greeter`.
# The human sets the API key (setup-jetson.sh or scripts/set-api-key.sh); never put it in code.
OPENAI_API_KEY=
# GREETER_BACKEND=openai        # openai | gemini | local
# GREETER_OPENAI_VOICE=marin
# GREETER_VOLUME=80
# GREETER_DIST_K=160            # set by: python -m greeter.robot.calibrate --stand-at 1 2 3
# GEMINI_API_KEY=               # optional hot standby (needs Python 3.10+)
# GREETER_RECORD=0              # stop recording audio/frames/transcripts for tuning
EOF
  )
fi
chmod 600 "$ENVF"
set_default() { grep -q "^$1=" "$ENVF" || echo "$1=$2" >>"$ENVF"; }
CAM=$("$PY" -c 'from greeter.robot.camera import find_usb_camera; print(find_usb_camera() or "")')
if [ -n "$CAM" ]; then set_default GREETER_CAMERA "$CAM"; else
  TODO+=("no USB camera found: plug the chest webcam into a USB-C port on the back-of-neck panel, then re-run install.sh")
fi
set_default GREETER_YOLO_MODEL "$YOLO_MODEL"
[ "$CPU_TORCH" = 1 ] && set_default GREETER_IMGSZ 416
[ "$WITH_LOCAL" = 1 ] && [ "$PYV" -ge 310 ] && set_default GREETER_VLM qwen3-vl:2b-instruct
grep -q '^OPENAI_API_KEY=.' "$ENVF" || grep -q '^GREETER_BACKEND=local' "$ENVF" ||
  TODO+=("OPENAI_API_KEY is empty: the human runs scripts/set-api-key.sh $USER@<jetson> on the laptop")

if grep -q '^OPENAI_API_KEY=.' "$ENVF"; then
  step "pre-recorded fallback lines (OpenAI TTS, once)"
  (set -a; . "$ENVF"; set +a; "$PY" -m greeter.clips --render) || TODO+=("could not render the fallback clips (the robot will speak them live)")
fi

step "self-test"
systemctl --user stop g1-greeter 2>/dev/null || true # it holds the camera
LD_LIBRARY_PATH="$EXTRA_LD" "$PY" -m greeter --check || TODO+=("self-test reported failures (see above)")

if [ "$SERVICE" = 1 ]; then
  step "systemd user service (starts at boot)"
  mkdir -p "$UNIT_DIR"
  cat >"$UNIT_DIR/g1-greeter.service" <<EOF
[Unit]
Description=G1 proactive greeter (all on the Jetson)
StartLimitIntervalSec=0

[Service]
WorkingDirectory=$APP
EnvironmentFile=-$ENVF
Environment=PYTHONUNBUFFERED=1
Environment=LD_LIBRARY_PATH=$EXTRA_LD
ExecStart=$PY -m greeter
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable g1-greeter >/dev/null
  if grep -q '^OPENAI_API_KEY=.' "$ENVF" || grep -q '^GREETER_BACKEND=local' "$ENVF"; then
    systemctl --user restart g1-greeter
    sleep 3
    systemctl --user --no-pager --lines=5 status g1-greeter || true
  fi
  loginctl show-user "$USER" -p Linger 2>/dev/null | grep -q yes ||
    TODO+=("linger is off, so the service won't start at boot: the human runs setup-jetson.sh")
fi

step "summary"
echo "logs:    journalctl --user -u g1-greeter -f"
echo "restart: systemctl --user restart g1-greeter"
if [ ${#TODO[@]} -gt 0 ]; then
  echo "still to do:"
  for t in "${TODO[@]}"; do echo "  - $t"; done
  exit 4
fi
echo "all done: the greeter starts automatically at boot"
