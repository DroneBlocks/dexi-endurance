#!/usr/bin/env python3
"""Tag ceiling test: a slow staircase climb over two tags, then down and land. One run per CH7 flip.

How high can the down camera still read a tag (dexi-gym notes/tag-altitude-nested.md predicts it)?
The flight bag records every camera frame and the rangefinder height; dexi-gym's
eval/tag_climb_score.py runs the detector offline on those frames at every decimate and for both
tag families, so one flight answers all of them.

Floor: tag36h11 ID 0 and the nested tagCustom48h12 (ID 0 with ID 1 inside) side by side, centers
25-30 cm apart, both flat, no glare (print them with tools/make_test_tags.py).

    tag_climb.py --top 3.5            CH7 mode (arm in Position on the ground between the two tags,
                                      flip CH7 to Offboard)
    tag_climb.py --top 3.5 --no-center   skip center_on_tag (an airframe without a tag_nav config,
                                      e.g. the DEXI-3): flow holds the takeoff point

The run:
  1. offboard_takeoff to START_M, center_on_tag on tag36h11 ID 0 (unless --no-center).
  2. fly_up STEP_M at a time to --top, holding DWELL_S at every step (height on the rangefinder).
  3. fly_down the same steps back to START_M, then PX4 Land straight down (the low end of the
     curve comes from the landing).
--top is required and must leave at least 1 m to the ceiling. Flow and the rangefinder are the
only position sources: above ~3 m flow gets noisy, expect the drone to wander 20-40 cm.
Abort: flip CH7 back to Position at any time (sticks do not override Offboard).
"""
import json, sys, time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import Bool, String
from px4_msgs.msg import VehicleStatus, VehicleLocalPosition, VehicleLandDetected
from dexi_interfaces.srv import FlightCommand, TagNavCommand

if '--top' not in sys.argv:
    sys.exit('usage: tag_climb.py --top <m> [--no-center]   (--top at least 1 m under the ceiling)')
TOP_M = float(sys.argv[sys.argv.index('--top') + 1])
CENTER = '--no-center' not in sys.argv
if not 1.0 <= TOP_M <= 6.0:
    sys.exit('--top must be 1-6 m')
TAG = 0
START_M = 0.8        # tags fit in the frame with margin; below this the landing covers it
STEP_M = 0.25
DWELL_S = 3.0        # ~75 frames per step at 25 fps
OFFBOARD = 14

rclpy.init()
node = Node('tag_climb')
s = {'nav': -1, 'armed': False, 'landed': True, 'rng': 0.0, 'tn': {}}
q = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=1)
def on_vs(m): s['nav'] = m.nav_state; s['armed'] = m.arming_state == 2
for t in ('/fmu/out/vehicle_status', '/fmu/out/vehicle_status_v1'):
    node.create_subscription(VehicleStatus, t, on_vs, q)
node.create_subscription(VehicleLocalPosition, '/fmu/out/vehicle_local_position_20hz', lambda m: s.__setitem__('rng', m.dist_bottom), q)
node.create_subscription(VehicleLandDetected, '/fmu/out/vehicle_land_detected', lambda m: s.__setitem__('landed', m.landed), q)
node.create_subscription(String, '/dexi/tag_nav/status', lambda m: s.__setitem__('tn', json.loads(m.data)), 10)
engage = node.create_publisher(Bool, '/dexi/tag_nav/engage', 10)
flight = node.create_client(FlightCommand, '/dexi/flight/command')
tagnav = node.create_client(TagNavCommand, '/dexi/tag_nav/command')
for c in (flight,) + ((tagnav,) if CENTER else ()):
    while not c.wait_for_service(timeout_sec=5.0):
        print(f'waiting for {c.srv_name}', flush=True)


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def call(client, req):
    f = client.call_async(req)
    rclpy.spin_until_future_complete(node, f)
    r = f.result()
    log(f'{req.command} {getattr(req, "value", "")}: {"ok" if r.success else "FAILED"} {r.message}')
    return r.success


def fc(cmd, value=0.0, timeout=0.0):
    r = FlightCommand.Request(); r.command = cmd; r.value = float(value); r.timeout = float(timeout)
    return call(flight, r)


def spin(sec):
    end = time.time() + sec
    while time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.02)


def still_ours():
    return s['armed'] and s['nav'] == OFFBOARD


def step(cmd):
    """One fly_up / fly_down step, then the dwell. False when the pilot took over or it failed."""
    if not still_ours() or not fc(cmd, value=STEP_M, timeout=10.0):
        return False
    spin(DWELL_S)
    log(f"dwell done at range {s['rng']:.2f} m")
    return still_ours()


def run():
    if not fc('offboard_takeoff', value=START_M, timeout=25.0) or not still_ours():
        log('takeoff did not complete: take over with CH7'); return
    if CENTER:
        engage.publish(Bool(data=True)); spin(0.3)
        r = TagNavCommand.Request(); r.command = 'center_on_tag'; r.tag_id = TAG; r.timeout = 20.0
        if not call(tagnav, r):
            log('could not center on tag 0: holding, take over with CH7'); return
        engage.publish(Bool(data=False)); spin(0.3)      # tag_nav off: the climb holds on flow
    n = max(0, round((TOP_M - START_M) / STEP_M))
    log(f'climbing {n} steps of {STEP_M} m to ~{START_M + n * STEP_M:.2f} m')
    for i in range(n):
        if not step('fly_up'):
            log('climb stopped: take over with CH7'); return
    log(f"top: range {s['rng']:.2f} m")
    for i in range(n):
        if not step('fly_down'):
            log('descent stopped: take over with CH7'); return
    fc('land', timeout=30.0)
    log('landed' if not s['armed'] else 'land returned with the aircraft still armed: take over')


fc('start_setpoint_stream')   # heartbeat without commanding Offboard, so PX4 accepts the CH7 flip
log(f'READY (top {TOP_M} m, center {CENTER}): arm in Position on the ground between the tags, flip CH7')
prev_nav = -1
while rclpy.ok():
    spin(0.05)
    flipped = s['nav'] == OFFBOARD and prev_nav not in (OFFBOARD, -1)
    prev_nav = s['nav']
    if flipped and s['armed'] and s['landed']:
        log('CH7 flipped on the ground: tag ceiling run')
        run()
        while s['armed']:
            spin(0.1)
        fc('start_setpoint_stream')
        prev_nav = s['nav']
        log('READY for another run: CH7 back to Position, re-arm, flip CH7')
