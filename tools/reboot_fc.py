#!/usr/bin/env python3
"""Reboot the flight controller over MAVLink (refuses if armed).

Restarting the DEXI stack can leave PX4's DDS client cut off from the restarted micro-ROS
agent. Rebooting only the flight controller reconnects it and keeps the companion's services.

    DEXI_HOST=<host> tools/reboot_fc.py
"""
import os, sys
from pymavlink import mavutil

host = os.environ.get('DEXI_HOST') or sys.exit('set DEXI_HOST')
m = mavutil.mavlink_connection(f'udpout:{host}:14550', source_system=254)
m.mav.heartbeat_send(6, 8, 0, 0, 0)
hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=10)
while hb and hb.get_srcComponent() != 1:
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=10)
if not hb:
    sys.exit(f'no heartbeat from {host}:14550')
if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
    sys.exit('armed: not rebooting')
m.mav.command_long_send(1, 1, mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN, 0, 1, 0, 0, 0, 0, 0, 0)
ack = m.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)
print('flight controller rebooting' if ack and ack.result == 0 else f'reboot not acknowledged: {ack}')
