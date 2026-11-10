#!/usr/bin/env bash
# Install the endurance test on a DEXI and start it.
#
#   drone/install.sh airframes/dexi5.yaml            # copy files, start hand-off + logger
#   drone/install.sh airframes/dexi5.yaml --no-start # copy files only
#
# Starts two transient systemd units on the CM4 (they do not survive a reboot; re-run after one):
#   ch7-tag0       streams setpoints and waits for CH7 -> Offboard, then centers and holds on tag 0
#   endurance-log  1 Hz samples + one summary per minute under /home/dexi/endurance/<start>/
# The CM4 must be on the ground and disarmed: restarting the DEXI stack cuts Offboard control.
set -euo pipefail
PROFILE=${1:?usage: install.sh airframes/<airframe>.yaml [--no-start]}
HERE=$(cd "$(dirname "$0")/.." && pwd)
HOST=${DEXI_HOST:-$(awk '/^host:/{print $2}' "$PROFILE")}
TAGCFG=$(awk '/^tag_nav_config:/{print $2}' "$PROFILE")
SSH="sshpass -p ${DEXI_PASS:-dexi} ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR dexi@$HOST"
SCP="sshpass -p ${DEXI_PASS:-dexi} scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

[ -f "$HERE/airframes/$TAGCFG" ] || { echo "missing airframes/$TAGCFG (measure the camera mount first)"; exit 1; }
$SCP "$HERE"/drone/ch7_center_tag0.py "$HERE"/drone/endurance_logger.py "$HERE"/drone/hgt_watch.py "dexi@$HOST:/home/dexi/"
$SCP "$HERE/airframes/$TAGCFG" "dexi@$HOST:/tmp/$TAGCFG"
$SSH "sudo cp /tmp/$TAGCFG /home/dexi/dexi_ws/install/dexi_apriltag/share/dexi_apriltag/config/$TAGCFG"
echo "installed on $HOST"
[ "${2:-}" = "--no-start" ] && exit 0

ROS='source /home/dexi/ros2_jazzy/install/setup.bash; source /home/dexi/dexi_ws/install/setup.bash'
ENVS='-E HOME=/root -E ROS_DOMAIN_ID=2 -E ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET'
$SSH "sudo systemctl restart dexi
      for i in \$(seq 1 60); do sudo journalctl -u dexi --since '-2 min' -o cat | grep -q 'tag_nav ready' && break; sleep 2; done
      sleep 5
      sudo systemd-run --unit=ch7-tag0 --collect $ENVS bash -c '$ROS; exec python3 -u /home/dexi/ch7_center_tag0.py'
      sudo systemd-run --unit=endurance-log --collect $ENVS bash -c '$ROS; exec python3 -u /home/dexi/endurance_logger.py'"
echo "started; run tools/preflight.sh $PROFILE before takeoff"
