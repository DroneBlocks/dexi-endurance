#!/usr/bin/env python3
"""One tag cycle: take off, center on tag 0, hover, land on tag 0.

    tag_cycle.py          CH7 mode: arm in Position on the ground near tag 0, flip CH7 to Offboard
                          -> one cycle. Flip CH7 back to Position, re-arm and flip again for the next.
    tag_cycle.py --now    one cycle right away: starts the heartbeat, arms and takes off by itself.
                          For calling from other code later. NOT FLOWN YET.

The cycle:
  1. offboard_takeoff to TAKEOFF_M (the DroneBlocks offboard manager's takeoff). Needs the EKF settings in airframes/dexi5.yaml (EKF2_BARO_NOISE 15,
     EKF2_TERR_NOISE 0.5); with stock baro settings the EKF height runs ~1.5 m ahead of the real one.
  2. tag_nav centers on tag 0 as soon as the takeoff reports done.
  3. hold over tag 0 for HOVER_S.
  4. land: PX4 Land straight down from the centered hold. PX4 disarms 2 s after touchdown.
Abort: flip CH7 back to Position at any time (sticks do not override Offboard). If centering or the
hold fails (tag lost), the aircraft keeps holding and the cycle stops: take it back and land by hand.
Every step is logged with a timestamp; the flight bag has the rest.
"""
import json, sys, time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import Bool, String
from px4_msgs.msg import VehicleStatus, VehicleLocalPosition, VehicleLandDetected
from dexi_interfaces.srv import FlightCommand, TagNavCommand

TAG = 0
TAKEOFF_M = 1.5      # standard test height
HOVER_S = 10.0
OFFBOARD = 14

rclpy.init()
node = Node('tag_cycle')
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
for c in (flight, tagnav):
    while not c.wait_for_service(timeout_sec=5.0):
        print(f'waiting for {c.srv_name}', flush=True)


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def call(client, req):
    f = client.call_async(req)
    rclpy.spin_until_future_complete(node, f)
    r = f.result()
    log(f'{req.command}: {"ok" if r.success else "FAILED"} {r.message}')
    return r.success


def fc(cmd, value=0.0, timeout=0.0):
    q = FlightCommand.Request(); q.command = cmd; q.value = float(value); q.timeout = float(timeout)
    return call(flight, q)


def tn(cmd, timeout=0.0, hold_s=0.0):
    q = TagNavCommand.Request(); q.command = cmd; q.tag_id = TAG; q.timeout = float(timeout); q.hold_s = float(hold_s)
    return call(tagnav, q)


def spin(sec):
    end = time.time() + sec
    while time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.02)


def offset_cm():
    o = s['tn'].get('offset') or {}
    return (o.get('forward', 0) ** 2 + o.get('right', 0) ** 2) ** 0.5 * 100 if o else float('nan')


def cycle():
    """Takeoff -> center -> hover -> land. True when it landed under its own control."""
    t0 = time.time()
    if not fc('offboard_takeoff', value=TAKEOFF_M, timeout=25.0) or s['nav'] != OFFBOARD:
        log('takeoff did not complete: holding, take over with CH7'); return False
    log(f"takeoff done: range {s['rng']:.2f} m, {time.time() - t0:.1f} s after the start")
    engage.publish(Bool(data=True)); spin(0.3)
    if not tn('center_on_tag', timeout=20.0):
        log('could not center on the tag: holding, take over with CH7'); return False
    if not tn('hold_on_tag', hold_s=HOVER_S):
        log('hold ended early: holding, take over with CH7'); return False
    log(f"landing from {s['rng']:.2f} m, tag offset {offset_cm():.1f} cm")
    last_seen = None
    ok = fc('land', timeout=30.0)
    # the bag has the whole descent; this is the last offset the camera saw on the way down
    if s['tn'].get('visible'):
        last_seen = offset_cm()
    log(f"landed {'ok' if ok else 'FAILED'} after {time.time() - t0:.1f} s"
        + (f', last tag offset seen {last_seen:.1f} cm' if last_seen is not None else ''))
    return ok


if '--now' in sys.argv:
    fc('start_offboard_heartbeat'); spin(1.0)
    if fc('arm'):
        cycle()
    sys.exit(0)

fc('start_setpoint_stream')   # heartbeat without commanding Offboard, so PX4 accepts the CH7 flip
log('READY: arm in Position on the ground near tag 0, then flip CH7 for one cycle')
prev_nav = -1
while rclpy.ok():
    spin(0.05)
    flipped = s['nav'] == OFFBOARD and prev_nav not in (OFFBOARD, -1)
    prev_nav = s['nav']
    if not (flipped and s['armed'] and s['landed']):
        continue
    log('CH7 flipped on the ground: cycle start')
    cycle()
    while s['armed'] and s['nav'] == OFFBOARD:     # stopped early: the pilot takes it back
        spin(0.1)
    while s['armed']:
        spin(0.1)
    fc('start_setpoint_stream')                     # the land stopped the heartbeat
    prev_nav = s['nav']
    log('READY for the next cycle: CH7 back to Position, re-arm, flip CH7')
