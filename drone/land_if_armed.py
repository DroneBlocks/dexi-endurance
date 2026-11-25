#!/usr/bin/env python3
"""Backstop land: if the aircraft is armed, airborne and in Offboard, command PX4 Land.

Runs as ExecStopPost of the tag-unattended unit (tools/unattended.sh), so it fires however
tag_unattended.py ends, including SIGKILL or a crash. The DEXI flight manager keeps streaming
setpoints after the script dies, so PX4's offboard-loss failsafe would never fire and the
aircraft would hold its last setpoint with nothing watching the tag.

It sends VEHICLE_CMD_NAV_LAND straight to PX4, not through the flight manager, so it works
with the manager hung. It does nothing when the aircraft is disarmed, landed, or in any mode
but Offboard (the pilot has it, or a land is already under way).
"""
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from px4_msgs.msg import VehicleStatus, VehicleLandDetected, VehicleCommand

OFFBOARD, LAND = 14, 18
WAIT_S = 3.0          # time to hear from PX4 before giving up
CONFIRM_S = 3.0       # time to see Land take effect

rclpy.init()
node = Node('land_if_armed')
s = {'nav': -1, 'armed': None, 'landed': None}
q = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=1)


def on_vs(m):
    s['nav'] = m.nav_state; s['armed'] = m.arming_state == 2


for t in ('/fmu/out/vehicle_status', '/fmu/out/vehicle_status_v1'):
    node.create_subscription(VehicleStatus, t, on_vs, q)
node.create_subscription(VehicleLandDetected, '/fmu/out/vehicle_land_detected', lambda m: s.__setitem__('landed', m.landed), q)
pub = node.create_publisher(VehicleCommand, '/fmu/in/vehicle_command', q)


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} land_if_armed: {msg}", flush=True)


def spin(sec):
    end = time.time() + sec
    while time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.02)


end = time.time() + WAIT_S
while time.time() < end and (s['armed'] is None or s['landed'] is None):
    spin(0.1)
if s['armed'] is None:
    log('no vehicle status from PX4: cannot check, nothing sent')
elif not s['armed'] or s['landed']:
    log('disarmed or landed: nothing to do')
elif s['nav'] != OFFBOARD:
    log(f"armed in nav_state {s['nav']}, not Offboard: the pilot or PX4 has it, nothing sent")
else:
    log('armed and airborne in Offboard with the script gone: commanding Land')
    vc = VehicleCommand()
    vc.command = VehicleCommand.VEHICLE_CMD_NAV_LAND
    vc.target_system = vc.target_component = vc.source_system = vc.source_component = 1
    vc.from_external = True
    end = time.time() + CONFIRM_S
    while time.time() < end and s['nav'] != LAND:
        vc.timestamp = node.get_clock().now().nanoseconds // 1000
        pub.publish(vc)
        spin(0.2)
    log('Land accepted' if s['nav'] == LAND else f"Land NOT confirmed (nav_state {s['nav']}): PX4 offboard-loss is the next layer")
