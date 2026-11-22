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
DOMAIN=$(awk '/^ros_domain:/{print $2}' "$PROFILE"); DOMAIN=${DOMAIN:-2}
MAVLINK=$(awk '/^mavlink:/{print $2}' "$PROFILE"); MAVLINK=${MAVLINK:-true}
fail=0
say() { printf '%-4s %s\n' "$1" "$2"; [ "$1" = ok ] || fail=1; }

echo "== PX4 parameters ($HOST)"
if [ "$MAVLINK" = false ]; then
  echo "skip (no MAVLink on this airframe): read the profile's params back in QGC over USB"
else
  $PY "$HERE/tools/params.py" check "$PROFILE" || fail=1
fi

echo "== companion"
$SSH true 2>/dev/null && say ok "ssh to $HOST" || { say FAIL "ssh to $HOST"; exit 1; }
for u in dexi ch7-tag0 endurance-log flight-bag; do
  [ "$($SSH systemctl is-active $u)" = active ] && say ok "$u running" || say FAIL "$u not running (drone/install.sh)"
done
# ch7_center_tag0.py parks tag_nav in wait_for_offboard; tag_cycle.py waits for the flip itself
$SSH "sudo journalctl -u dexi -b -o cat | grep -q 'waiting for hand-off' || sudo journalctl -u ch7-tag0 -b -o cat | grep -q 'READY'" && say ok "hand-off script waiting for CH7" || say FAIL "hand-off script not waiting for CH7"
$SSH "sudo HOME=/root ROS_DOMAIN_ID=$DOMAIN bash -c 'source /home/dexi/ros2_jazzy/install/setup.bash; source /home/dexi/dexi_ws/install/setup.bash;
      for t in vehicle_status_v1 vehicle_status; do timeout 6 ros2 topic echo --once /fmu/out/\$t px4_msgs/msg/VehicleStatus --qos-reliability best_effort --field nav_state; done' | grep -q '[0-9]'" \
  && say ok "PX4 data reaching ROS" || say FAIL "no PX4 data in ROS (power cycle the aircraft)"
$SSH "sudo HOME=/root ROS_DOMAIN_ID=$DOMAIN bash -c 'source /home/dexi/ros2_jazzy/install/setup.bash; source /home/dexi/dexi_ws/install/setup.bash;
      timeout 8 ros2 topic echo --once /fmu/out/failsafe_flags px4_msgs/msg/FailsafeFlags --qos-reliability best_effort --field offboard_control_signal_lost' | head -1 | grep -q False" \
  && say ok "PX4 receiving the offboard heartbeat" || say FAIL "PX4 not receiving the offboard heartbeat (power cycle the aircraft)"
TAGCFG=$(awk '/^tag_nav_config:/{print $2}' "$PROFILE")
if grep -q 'align_yaw: true' "$HERE/airframes/$TAGCFG"; then
  $SSH "sudo HOME=/root ROS_DOMAIN_ID=$DOMAIN bash -c 'source /home/dexi/ros2_jazzy/install/setup.bash; source /home/dexi/dexi_ws/install/setup.bash;
        ros2 param get /tag_nav align_yaw --no-daemon'" | grep -q True && say ok "tag_nav align_yaw on" || say FAIL "tag_nav align_yaw off"
fi
D=$($SSH 'ls -d /home/dexi/endurance/*/ | sort | tail -1')
$SSH "find $D/samples.csv -newermt '-10 seconds' | grep -q ." && say ok "logger writing $D" || say FAIL "logger not writing"

[ $fail = 0 ] && echo "PREFLIGHT OK" || { echo "PREFLIGHT FAILED"; exit 1; }
