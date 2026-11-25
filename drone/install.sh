#!/usr/bin/env bash
# Install the endurance test on a DEXI and start it.
#
#   drone/install.sh airframes/dexi5.yaml            # copy files, start hand-off + logger
#   drone/install.sh airframes/dexi5.yaml --no-start # copy files only
#   HANDOFF=ch7_autotakeoff_tag0.py drone/install.sh airframes/dexi5.yaml   # CH7 on the ground = auto takeoff
#   NORESTART=1 drone/install.sh airframes/dexi3.yaml  # start the units on the running stack (after a power cycle)
#
# Starts three transient systemd units on the CM4 (they do not survive a reboot; re-run after one):
#   ch7-tag0       streams setpoints and waits for CH7 -> Offboard, then centers and holds on tag 0
#   endurance-log  1 Hz samples + one summary per minute under /home/dexi/endurance/<start>/
#   flight-bag     one ROS 2 bag per flight, arm to disarm, under /home/dexi/flight_bags/
# The CM4 must be on the ground and disarmed: restarting the DEXI stack cuts Offboard control.
set -euo pipefail
PROFILE=${1:?usage: install.sh airframes/<airframe>.yaml [--no-start]}
HERE=$(cd "$(dirname "$0")/.." && pwd)
HOST=${DEXI_HOST:-$(awk '/^host:/{print $2}' "$PROFILE")}
TAGCFG=$(awk '/^tag_nav_config:/{print $2}' "$PROFILE")
DOMAIN=$(awk '/^ros_domain:/{print $2}' "$PROFILE"); DOMAIN=${DOMAIN:-2}
MAVLINK=$(awk '/^mavlink:/{print $2}' "$PROFILE"); MAVLINK=${MAVLINK:-true}
SSH="sshpass -p ${DEXI_PASS:-dexi} ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR dexi@$HOST"
SCP="sshpass -p ${DEXI_PASS:-dexi} scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

[ -f "$HERE/airframes/$TAGCFG" ] || { echo "missing airframes/$TAGCFG (measure the camera mount first)"; exit 1; }
$SCP "$HERE"/drone/*.py "$HERE"/drone/*.sh "dexi@$HOST:/home/dexi/"
$SSH "chmod +x /home/dexi/run_ros.sh"
$SCP "$HERE/airframes/$TAGCFG" "dexi@$HOST:/tmp/$TAGCFG"
$SSH "sudo cp /tmp/$TAGCFG /home/dexi/dexi_ws/install/dexi_apriltag/share/dexi_apriltag/config/$TAGCFG"
# Turn tag_nav on with this airframe's config in the user config the DEXI stack reads first
$SSH "f=/home/dexi/.dexi-config.yaml; grep -q '^  tag_nav:' \$f || sed -i 's/^nodes:\$/nodes:\n  tag_nav:\n    enabled: true\n    config: $TAGCFG/' \$f
      sed -i '/^  tag_nav:/,/^  [a-z]/{s/^    enabled: .*/    enabled: true/;s/^    config: .*/    config: $TAGCFG/}' \$f"
echo "installed on $HOST"
[ "${2:-}" = "--no-start" ] && exit 0

ROS='source /home/dexi/ros2_jazzy/install/setup.bash; source /home/dexi/dexi_ws/install/setup.bash'
ENVS="-E HOME=/root -E ROS_DOMAIN_ID=$DOMAIN -E ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET"
$SSH "sudo systemctl stop ch7-tag0 ch7-autotakeoff endurance-log flight-bag 2>/dev/null; sudo systemctl reset-failed ch7-tag0 ch7-autotakeoff endurance-log flight-bag 2>/dev/null
      # the DEXI stack and the units below must share one ROS domain, and no other aircraft on the network may use it
      sudo mkdir -p /etc/systemd/system/dexi.service.d
      printf '[Service]\\nEnvironment=ROS_DOMAIN_ID=$DOMAIN\\n' | sudo tee /etc/systemd/system/dexi.service.d/ros-domain.conf >/dev/null
      sudo systemctl daemon-reload
      [ '${NORESTART:-}' = 1 ] || sudo systemctl restart dexi
      for i in \$(seq 1 60); do sudo journalctl -u dexi --since '-2 min' -o cat | grep -q 'tag_nav ready' && break; sleep 2; done
      sleep 5
      sudo systemd-run --unit=ch7-tag0 --collect $ENVS bash -c '$ROS; exec python3 -u /home/dexi/${HANDOFF:-ch7_center_tag0.py}'
      sudo systemd-run --unit=endurance-log --collect $ENVS bash -c '$ROS; exec python3 -u /home/dexi/endurance_logger.py'
      sudo systemd-run --unit=flight-bag --collect $ENVS bash -c '$ROS; exec python3 -u /home/dexi/flight_bag.py'"
# The stack restart can leave PX4's DDS client cut off from the new micro-ROS agent.
# Rebooting only the flight controller reconnects it and keeps the units above running.
# No MAVLink to the FC (mavlink: false, e.g. a UWB tag on that UART): power cycle the aircraft instead.
if [ "${NORESTART:-}" = 1 ]; then
  :
elif [ "$MAVLINK" = false ]; then
  echo "no MAVLink on this airframe: power cycle the aircraft if preflight shows no PX4 data in ROS"
else
  DEXI_HOST=$HOST python3 "$HERE/tools/reboot_fc.py" && sleep 40
fi
echo "started; run tools/preflight.sh $PROFILE before takeoff"
