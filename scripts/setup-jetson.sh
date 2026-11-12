#!/usr/bin/env bash
# The only script the human runs (once). From the laptop, with an Ethernet cable to the robot:
#
#   scp scripts/setup-jetson.sh unitree@192.168.123.164:~ && ssh -t unitree@192.168.123.164 'sudo bash ~/setup-jetson.sh'
#
# (Copy it over first: piping it into `ssh -t` leaves sudo and the prompts without a terminal.)
#
# It asks for three things: the sudo password, the Wi-Fi name + password (a pocket 4G/5G
# router with a data SIM, or a phone hotspot), and the OpenAI API key (hidden). It then:
#   1. connects the Jetson to the internet over Wi-Fi (robot network stays on eth0),
#   2. installs build tools with apt,
#   3. lets the greeter run at boot without a login (linger) and gives camera/audio access,
#   4. stores the API key in ~/.config/g1-greeter/greeter.env (mode 600).
# Everything after this (code, models, service) is installed without sudo by scripts/deploy.sh.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "please run with sudo (see the comment at the top)"; exit 1; }
U=${SUDO_USER:-unitree}
H=$(getent passwd "$U" | cut -d: -f6)
ask() { local v; read -r -p "$1" v </dev/tty; printf '%s' "$v"; }
ask_secret() { local v; read -r -s -p "$1" v </dev/tty; echo >/dev/tty; printf '%s' "$v"; }
online() { curl -s --max-time 6 -o /dev/null https://api.openai.com/v1/models; }

echo "== 1/4 internet over Wi-Fi"
if online; then
  echo "already online"
else
  rfkill unblock all || true
  nmcli radio wifi on || true
  sleep 3
  nmcli -f SSID,SIGNAL,SECURITY dev wifi list --rescan yes 2>/dev/null | head -15 || true
  SSID=$(ask "Wi-Fi name (pocket 4G/5G router or phone hotspot; eduroam will not work): ")
  PASS=$(ask_secret "Wi-Fi password (hidden): ")
  nmcli dev wifi connect "$SSID" password "$PASS"
  for _ in $(seq 1 20); do online && break; sleep 1; done
  if ! online; then
    # The robot's internal network must not be the default route: send internet traffic over Wi-Fi.
    GW_DEV=$(ip route show default | awk '/default/ {print $5; exit}')
    if [ -n "$GW_DEV" ] && ! nmcli -t -f DEVICE,TYPE dev | grep -q "^$GW_DEV:wifi"; then
      CON=$(nmcli -t -f NAME,DEVICE con show --active | awk -F: -v d="$GW_DEV" '$2==d {print $1; exit}')
      if [ -n "$CON" ]; then
        nmcli con mod "$CON" ipv4.never-default yes && nmcli con up "$CON" >/dev/null
      else
        ip route del default dev "$GW_DEV" || true
        echo "note: removed the default route via $GW_DEV until reboot (it is not managed by NetworkManager)"
      fi
    fi
    for _ in $(seq 1 10); do online && break; sleep 1; done
  fi
  online || { echo "still no internet: check the 4G router (or hotspot) and run this script again"; exit 2; }
fi
nmcli con mod "$(nmcli -t -f NAME,TYPE con show --active | awk -F: '$2 ~ /wireless/ {print $1; exit}')" connection.autoconnect yes 2>/dev/null || true

echo "== 2/4 system packages"
apt-get update
apt-get install -y --no-install-recommends \
  git cmake build-essential python3-dev curl zstd v4l-utils espeak-ng libopenblas-dev libopenmpi-dev avahi-daemon libportaudio2

echo "== 3/4 start at boot, camera and audio access"
loginctl enable-linger "$U"
usermod -aG video,audio "$U"
RULES=/etc/udev/rules.d/99-realsense-libusb.rules  # lets the greeter open the head D435i without root
if [ ! -f "$RULES" ]; then
  curl -fsSL https://raw.githubusercontent.com/IntelRealSense/librealsense/master/config/99-realsense-libusb.rules -o "$RULES" &&
    udevadm control --reload-rules && udevadm trigger || echo "note: could not install the RealSense udev rules"
fi

echo "== 4/4 OpenAI API key"
KEY=$(ask_secret "OpenAI API key from platform.openai.com (sk-..., hidden; Enter to skip): ")
if [ -n "$KEY" ]; then
  install -d -m 700 -o "$U" -g "$U" "$H/.config" "$H/.config/g1-greeter"
  ENVF="$H/.config/g1-greeter/greeter.env"
  touch "$ENVF"
  { grep -v '^OPENAI_API_KEY=' "$ENVF" || true; printf 'OPENAI_API_KEY=%s\n' "$KEY"; } >"$ENVF.new"
  mv "$ENVF.new" "$ENVF"
  chown "$U:$U" "$ENVF"
  chmod 600 "$ENVF"
  echo "key stored in $ENVF"
fi

WIFI_DEV=$(nmcli -t -f DEVICE,TYPE dev | awk -F: '$2=="wifi" {print $1; exit}')
WIFI_IP=$(nmcli -g IP4.ADDRESS dev show "$WIFI_DEV" 2>/dev/null | head -1 | cut -d/ -f1)
echo
echo "done. Jetson Wi-Fi address: ${WIFI_IP:-unknown}  (also: $(hostname).local)"
echo "tell Claude: the robot is ready at $U@${WIFI_IP:-192.168.123.164}"
