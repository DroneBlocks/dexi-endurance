#!/usr/bin/env bash
# Start, land or watch an unattended tag hold from the laptop (no transmitter input needed).
#
#   tools/unattended.sh airframes/dexi5.yaml start [tag_unattended.py args]   # e.g. start --tag 8 --hover 180
#   tools/unattended.sh airframes/dexi5.yaml land     # SIGTERM: the script lands and exits
#   tools/unattended.sh airframes/dexi5.yaml kill     # SIGKILL: failsafe test, the backstop lands it
#   tools/unattended.sh airframes/dexi5.yaml log      # follow the script's log
#
# The script runs as the transient unit tag-unattended. Its ExecStopPost is land_if_armed.py,
# so however the script ends (land, crash, SIGKILL) an aircraft left armed in Offboard is landed.
# Needs drone/install.sh to have copied the drone/ scripts first.
set -euo pipefail
PROFILE=${1:?usage: unattended.sh airframes/<airframe>.yaml start|land|kill|log [args]}
CMD=${2:?usage: unattended.sh airframes/<airframe>.yaml start|land|kill|log [args]}
shift 2
HOST=${DEXI_HOST:-$(awk '/^host:/{print $2}' "$PROFILE")}
SSH="sshpass -p ${DEXI_PASS:-dexi} ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=8 dexi@$HOST"
ENVS='-E HOME=/root -E ROS_DOMAIN_ID=2 -E ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET'
UNIT=tag-unattended
FOLLOW="sudo journalctl -u $UNIT -f -o cat --since '-5 s'"

case $CMD in
  start)
    $SSH "systemctl is-active --quiet $UNIT && { echo '$UNIT is already running'; exit 1; }
          sudo systemctl reset-failed $UNIT 2>/dev/null
          sudo systemd-run --unit=$UNIT --collect $ENVS \
            -p ExecStopPost='/home/dexi/run_ros.sh /home/dexi/land_if_armed.py' \
            /home/dexi/run_ros.sh /home/dexi/tag_unattended.py $*"
    $SSH "$FOLLOW" ;;
  land) $SSH "sudo systemctl kill -s TERM $UNIT"; $SSH "$FOLLOW" ;;
  kill) $SSH "sudo systemctl kill -s KILL $UNIT"; $SSH "$FOLLOW" ;;
  log)  $SSH "$FOLLOW" ;;
  *) echo "unknown command $CMD (start|land|kill|log)"; exit 1 ;;
esac
