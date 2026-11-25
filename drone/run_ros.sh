#!/usr/bin/env bash
# Run a Python script with the DEXI ROS 2 environment: run_ros.sh <script.py> [args...]
# Used by tools/unattended.sh so systemd can start the script and its ExecStopPost backstop.
source /home/dexi/ros2_jazzy/install/setup.bash
source /home/dexi/dexi_ws/install/setup.bash
exec python3 -u "$@"
