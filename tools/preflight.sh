#!/usr/bin/env bash
# Preflight for an endurance run. Every line must read ok before takeoff.
#
#   tools/preflight.sh airframes/dexi5.yaml
set -uo pipefail
PROFILE=${1:?usage: preflight.sh airframes/<airframe>.yaml}
HERE=$(cd "$(dirname "$0")/.." && pwd)
HOST=${DEXI_HOST:-$(awk '/^host:/{print $2}' "$PROFILE")}
SSH="sshpass -p ${DEXI_PASS:-dexi} ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=8 dexi@$HOST"
PY=${PYTHON:-python3}
fail=0
say() { printf '%-4s %s\n' "$1" "$2"; [ "$1" = ok ] || fail=1; }

echo "== PX4 parameters ($HOST)"
$PY "$HERE/tools/params.py" check "$PROFILE" || fail=1

echo "== companion"
$SSH true 2>/dev/null && say ok "ssh to $HOST" || { say FAIL "ssh to $HOST"; exit 1; }
for u in dexi ch7-tag0 endurance-log; do
  [ "$($SSH systemctl is-active $u)" = active ] && say ok "$u running" || say FAIL "$u not running (drone/install.sh)"
done
$SSH "sudo journalctl -u dexi -b -o cat | grep -q 'waiting for hand-off'" && say ok "tag_nav waiting for CH7" || say FAIL "tag_nav not waiting for hand-off"
$SSH "sudo HOME=/root ROS_DOMAIN_ID=2 bash -c 'source /home/dexi/ros2_jazzy/install/setup.bash; source /home/dexi/dexi_ws/install/setup.bash;
      timeout 8 ros2 topic echo --once /fmu/out/vehicle_status_v1 px4_msgs/msg/VehicleStatus --qos-reliability best_effort --field nav_state' | grep -q '[0-9]'" \
  && say ok "PX4 data reaching ROS" || say FAIL "no PX4 data in ROS (power cycle the aircraft)"
$SSH "sudo HOME=/root ROS_DOMAIN_ID=2 bash -c 'source /home/dexi/ros2_jazzy/install/setup.bash; source /home/dexi/dexi_ws/install/setup.bash;
      ros2 param get /tag_nav align_yaw --no-daemon'" | grep -q True && say ok "tag_nav align_yaw on" || say FAIL "tag_nav align_yaw off"
D=$($SSH 'ls -d /home/dexi/endurance/*/ | sort | tail -1')
$SSH "find $D/samples.csv -newermt '-10 seconds' | grep -q ." && say ok "logger writing $D" || say FAIL "logger not writing"

[ $fail = 0 ] && echo "PREFLIGHT OK" || { echo "PREFLIGHT FAILED"; exit 1; }
