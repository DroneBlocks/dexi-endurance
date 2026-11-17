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
from px4_msgs.msg import VehicleStatus, VehicleLocalPosition, VehicleLandDetected, VehicleCommand
from dexi_interfaces.srv import FlightCommand, TagNavCommand

TAG = 0
TAKEOFF_M = 1.5      # standard test height
HOVER_S = 10.0
OFFBOARD = 14
LAND, DESCEND = 18, 12
GROUND_M = 0.20      # forced-disarm backstop: height under this ...
GROUND_S = 6.0       # ... for this long (PX4 normally disarms 3-5 s after touchdown) ...
# --ground-s S: shorter backstop. DEXI-3 2026-11-16: the EKF velocity ran away 0.2 s after touchdown and
# PX4, still armed, dragged the aircraft ~0.6 m across the floor before its land detector fired (5.8 s).
if '--ground-s' in sys.argv: GROUND_S = float(sys.argv[sys.argv.index('--ground-s') + 1])
# --ground-s S: shorter backstop. DEXI-3 2026-11-16: the EKF velocity ran away 0.2 s after touchdown and
# PX4, still armed, dragged the aircraft ~0.6 m across the floor before its land detector fired (5.8 s).
if '--ground-s' in sys.argv: GROUND_S = float(sys.argv[sys.argv.index('--ground-s') + 1])
LAND_MIN_S = 3.0     # ... and at least this long after the land started
# --land-min-s S: allow the backstop sooner after the land starts (DEXI-3: 1.0)
if '--land-min-s' in sys.argv: LAND_MIN_S = float(sys.argv[sys.argv.index('--land-min-s') + 1])
CENTER_M = 0.05     # land only once the tag reads within this of center ...
CENTER_WAIT_S = 3.0 # ... waiting up to this long for it after the hold
# --repeat N: one CH7 flip runs N cycles; between them it waits REST_S on the ground, re-arms
# itself and goes again. Flip CH7 back to Position at any time to stop after the current step.
REPEAT = int(sys.argv[sys.argv.index('--repeat') + 1]) if '--repeat' in sys.argv else 1
REST_S = 15.0       # 2026-11-16: recorder needs time to restart between cycles (dexi-gym #4)

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
cmd_pub = node.create_publisher(VehicleCommand, '/fmu/in/vehicle_command', q)
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


def force_disarm():
    vc = VehicleCommand()
    vc.command = VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM
    vc.param1, vc.param2 = 0.0, 21196.0             # disarm, forced: skips the land detector like the kill switch
    vc.target_system = vc.target_component = vc.source_system = vc.source_component = 1
    vc.from_external = True
    for _ in range(3):
        vc.timestamp = node.get_clock().now().nanoseconds // 1000
        cmd_pub.publish(vc); spin(0.1)


def land():
    """PX4 Land, with a backstop for when the land detector never confirms.

    At touchdown flow drops out, and if the EKF velocity then runs away the land detector
    keeps the aircraft armed on the ground (2026-11-13). If the height has stayed under
    GROUND_M for GROUND_S, at least LAND_MIN_S after the land started, it disarms (forced).
    """
    q = FlightCommand.Request(); q.command = 'land'; q.value = 0.0; q.timeout = 30.0
    f = flight.call_async(q)
    t0, low_since, forced = time.time(), None, False
    while not f.done():
        rclpy.spin_once(node, timeout_sec=0.05)
        on_ground = s['armed'] and s['nav'] in (LAND, DESCEND) and s['rng'] < GROUND_M
        if not forced and on_ground and time.time() - t0 >= LAND_MIN_S:
            low_since = low_since or time.time()
            if time.time() - low_since >= GROUND_S:
                log(f"on the ground {GROUND_S:.1f} s (height {s['rng']:.2f} m) and still armed: forced disarm")
                force_disarm(); forced = True
        else:
            low_since = None
    r = f.result()
    log(f'land: {"ok" if r.success else "FAILED"} {r.message}' + (' (forced disarm)' if forced else ''))
    return r.success


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
    # land from the center: keep holding in 0.5 s steps until the tag reads within CENTER_M (max CENTER_WAIT_S)
    t1 = time.time()
    while offset_cm() > CENTER_M * 100 and time.time() - t1 < CENTER_WAIT_S:
        if not tn('hold_on_tag', hold_s=0.5): break
    log(f"landing from {s['rng']:.2f} m, tag offset {offset_cm():.1f} cm")
    last_seen = None
    ok = land()
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
    log(f'CH7 flipped on the ground: {REPEAT} cycle(s)')
    for n in range(1, REPEAT + 1):
        if n > 1:
            # next cycle only if the last one landed, CH7 still says Offboard and the pilot did nothing
            fc('start_setpoint_stream')                 # the land stopped the heartbeat; PX4 returns to Offboard on it
            spin(REST_S)
            if s['nav'] != OFFBOARD or s['armed'] or not s['landed']:
                log(f'cycle {n} not started: CH7 left Offboard or the aircraft is not landed and disarmed'); break
            fc('start_offboard_heartbeat'); spin(1.0)
            if s['nav'] != OFFBOARD or not fc('arm'):
                log(f'cycle {n} not started: arm failed or CH7 left Offboard'); break
            spin(1.0)
        log(f'cycle {n}/{REPEAT}')
        ok = cycle()
        while s['armed'] and s['nav'] == OFFBOARD:     # stopped early: the pilot takes it back
            spin(0.1)
        while s['armed']:
            spin(0.1)
        if not ok:
            break
    fc('start_setpoint_stream')                     # the land stopped the heartbeat
    prev_nav = s['nav']
    log('READY for the next cycle: CH7 back to Position, re-arm, flip CH7')
