#!/usr/bin/env python3
"""Record one ROS 2 bag per flight: starts on arm, stops 5 s after disarm.

A recorder is kept running paused while disarmed and resumed on arm. Starting a recorder
takes ~4 s (topic discovery), which on 2026-11-12 cost the whole liftoff: the first message
came with the aircraft already 0.5 m up. A paused recorder resumes at once.

Bags go to /home/dexi/flight_bags/<arm time YYYY-MM-DD_HHMMSS>/ (MCAP, split every hour).
Covers takeoff, the tag hold and landing: the tag camera, detections, tag_nav status and
setpoints, PX4 state and pilot sticks. Mostly camera: about 2 GB per hour.
"""
import os, shutil, signal, subprocess, time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from px4_msgs.msg import VehicleStatus
from rosbag2_interfaces.srv import Resume

OUT = '/home/dexi/flight_bags'
STOP_DELAY = 5.0
REC_NODE = 'flight_bag_recorder'
TOPICS = [
    # tag camera and detector
    '/cam0/image_raw/compressed', '/cam0/camera_info', '/apriltag_detections', '/tf', '/tf_static',
    # what tag_nav saw and asked for
    '/dexi/tag_nav/status', '/dexi/tag_nav/engage', '/dexi/offboard_manager', '/dexi/offboard_manager/status',
    '/fmu/in/trajectory_setpoint', '/fmu/in/offboard_control_mode', '/fmu/in/vehicle_command',
    # what the aircraft did
    '/fmu/out/vehicle_status', '/fmu/out/vehicle_status_v1', '/fmu/out/vehicle_land_detected',
    # 100 Hz state (IMU, attitude, odometry) is in the flight controller log; the bag keeps a 20 Hz
    # position copy for lining the two up and for quick looks. Recording the 100 Hz topics cost
    # the recorder most of a core.
    '/fmu/out/vehicle_local_position_20hz', '/fmu/out/estimator_status_flags', '/fmu/out/battery_status',
    '/fmu/out/manual_control_setpoint', '/fmu/out/failsafe_flags', '/rosout',
]

rclpy.init()
node = Node('flight_bag')
state = {'armed': False}
q = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=1)
for topic in ('/fmu/out/vehicle_status', '/fmu/out/vehicle_status_v1'):
    node.create_subscription(VehicleStatus, topic, lambda m: state.__setitem__('armed', m.arming_state == 2), q)

resume_cli = node.create_client(Resume, f'/{REC_NODE}/resume')
os.makedirs(OUT, exist_ok=True)


def warm():
    """Start a paused recorder, ready for the next arm."""
    path = os.path.join(OUT, time.strftime('%Y-%m-%d_%H%M%S'))
    p = subprocess.Popen(['ros2', 'bag', 'record', '-s', 'mcap', '--max-bag-duration', '3600',
                          '--start-paused', '--node-name', REC_NODE, '-o', path] + TOPICS,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    resume_cli.wait_for_service(timeout_sec=30)
    print(f'recorder ready (paused): {path}', flush=True)
    return {'p': p, 'path': path, 'used': False}


def stop(rec):
    rec['p'].send_signal(signal.SIGINT)
    try:
        rec['p'].wait(timeout=30)
    except subprocess.TimeoutExpired:
        rec['p'].kill()
    if not rec['used']:
        shutil.rmtree(rec['path'], ignore_errors=True)   # never armed: drop the empty bag
    else:
        final = os.path.join(OUT, rec['armed_at'])     # name the bag by its arm time
        os.rename(rec['path'], final)
        print(f"recording stopped: {final}", flush=True)


def shutdown(*_):
    stop(rec)
    raise SystemExit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
rec, disarmed_at = warm(), None
while True:
    rclpy.spin_once(node, timeout_sec=0.05)
    if rec['p'].poll() is not None:             # recorder died: replace it
        rec = warm()
    if state['armed']:
        disarmed_at = None
        if not rec['used']:
            resume_cli.call_async(Resume.Request())
            rec['used'] = True
            rec['armed_at'] = time.strftime('%Y-%m-%d_%H%M%S')
            print(f"armed: recording {rec['path']}", flush=True)
    elif rec['used']:
        disarmed_at = disarmed_at or time.time()
        if time.time() - disarmed_at >= STOP_DELAY:
            stop(rec)
            rec, disarmed_at = warm(), None
