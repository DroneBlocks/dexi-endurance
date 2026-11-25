#!/usr/bin/env python3
"""Unattended tag hold: arm, take off, center on tag 0 and hold, with no transmitter input.

    tag_unattended.py [--hover S] [--loss S] [--height M] [--tag N]

    --hover S    land after S seconds in the hold (default 60; 0 = hold until told to land)
    --loss S     land when tag 0 has not been seen for S seconds (default 5)
    --height M   takeoff height (default 1.5)
    --tag N      tag id to hold over (default 0; 8 = the nested pad's outer tag, with the detector set to tagCustom48h12)

Started over the network with the aircraft on the ground, disarmed, tag 0 under the camera:
  1. arm and offboard_takeoff to the height (the same self-arm and takeoff tag_cycle.py --repeat flies).
  2. center on tag 0, then hold over it.
  3. land (PX4 Land, straight down) when any of these happens:
       - tag 0 unseen for --loss seconds, or tag_nav stops reporting
       - the takeoff, the centering or the hold fails
       - the hover time is up
       - the script gets SIGINT or SIGTERM (the network "land now")
Pilot takeover: any mode change on the transmitter takes the aircraft out of Offboard. The
script then stops and commands nothing more. CH7 must be in the Position (low) position at
the start.
If this script is killed outright (SIGKILL, CM4 crash) nothing here lands the aircraft; that
is PX4's offboard-loss failsafe, tested separately.
"""
import json, signal, sys, time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import Bool, String
from px4_msgs.msg import VehicleStatus, VehicleLocalPosition, VehicleLandDetected, VehicleCommand
from dexi_interfaces.srv import FlightCommand, TagNavCommand


def arg(name, default):
    return float(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


TAG = int(arg('--tag', 0))
HOVER_S = arg('--hover', 60.0)
LOSS_S = arg('--loss', 5.0)
TAKEOFF_M = arg('--height', 1.5)
HOLD_CHUNK_S = 30.0
OFFBOARD = 14
LAND, DESCEND = 18, 12
GROUND_M = 0.20      # forced-disarm backstop, as in tag_cycle.py: height under this ...
GROUND_S = 6.0       # ... for this long ...
LAND_MIN_S = 3.0     # ... and at least this long after the land started

rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
node = Node('tag_unattended')
s = {'nav': -1, 'armed': False, 'landed': True, 'rng': 0.0, 'tn': {}, 'seen': 0.0, 'stop': None}
q = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=1)


def on_vs(m):
    s['nav'] = m.nav_state; s['armed'] = m.arming_state == 2


def on_tn(m):
    s['tn'] = json.loads(m.data)
    if s['tn'].get('visible'):
        s['seen'] = time.time()


for t in ('/fmu/out/vehicle_status', '/fmu/out/vehicle_status_v1'):
    node.create_subscription(VehicleStatus, t, on_vs, q)
node.create_subscription(VehicleLocalPosition, '/fmu/out/vehicle_local_position_20hz', lambda m: s.__setitem__('rng', m.dist_bottom), q)
node.create_subscription(VehicleLandDetected, '/fmu/out/vehicle_land_detected', lambda m: s.__setitem__('landed', m.landed), q)
node.create_subscription(String, '/dexi/tag_nav/status', on_tn, 10)
engage = node.create_publisher(Bool, '/dexi/tag_nav/engage', 10)
cmd_pub = node.create_publisher(VehicleCommand, '/fmu/in/vehicle_command', q)
flight = node.create_client(FlightCommand, '/dexi/flight/command')
tagnav = node.create_client(TagNavCommand, '/dexi/tag_nav/command')
for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, lambda n, f: s.__setitem__('stop', signal.Signals(n).name))


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def spin(sec):
    end = time.time() + sec
    while time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.02)


def call(client, req):
    f = client.call_async(req)
    while not f.done():
        rclpy.spin_once(node, timeout_sec=0.05)
    r = f.result()
    log(f'{req.command}: {"ok" if r.success else "FAILED"} {r.message}')
    return r.success


def fc(cmd, value=0.0, timeout=0.0):
    r = FlightCommand.Request(); r.command = cmd; r.value = float(value); r.timeout = float(timeout)
    return call(flight, r)


def tn_req(cmd, timeout=0.0, hold_s=0.0):
    r = TagNavCommand.Request(); r.command = cmd; r.tag_id = TAG; r.timeout = float(timeout); r.hold_s = float(hold_s)
    return r


def offset_cm():
    o = s['tn'].get('offset') or {}
    return (o.get('forward', 0) ** 2 + o.get('right', 0) ** 2) ** 0.5 * 100 if o else float('nan')


def pilot_has_it():
    return s['armed'] and s['nav'] not in (OFFBOARD, LAND, DESCEND)


def force_disarm():
    vc = VehicleCommand()
    vc.command = VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM
    vc.param1, vc.param2 = 0.0, 21196.0             # disarm, forced: skips the land detector like the kill switch
    vc.target_system = vc.target_component = vc.source_system = vc.source_component = 1
    vc.from_external = True
    for _ in range(3):
        vc.timestamp = node.get_clock().now().nanoseconds // 1000
        cmd_pub.publish(vc); spin(0.1)


def land(why):
    """PX4 Land with tag_cycle.py's backstop: forced disarm if it sits on the ground still armed."""
    log(f"LAND: {why} (height {s['rng']:.2f} m, tag offset {offset_cm():.1f} cm)")
    engage.publish(Bool(data=False)); spin(0.3)     # stands down any tag_nav job before the land
    r = FlightCommand.Request(); r.command = 'land'; r.value = 0.0; r.timeout = 30.0
    f = flight.call_async(r)
    t0, low_since, forced = time.time(), None, False
    while not f.done():
        rclpy.spin_once(node, timeout_sec=0.05)
        if pilot_has_it():
            log('pilot took over during the land: standing down'); return False
        on_ground = s['armed'] and s['nav'] in (LAND, DESCEND) and s['rng'] < GROUND_M
        if not forced and on_ground and time.time() - t0 >= LAND_MIN_S:
            low_since = low_since or time.time()
            if time.time() - low_since >= GROUND_S:
                log(f"on the ground {GROUND_S:.0f} s (height {s['rng']:.2f} m) and still armed: forced disarm")
                force_disarm(); forced = True
        else:
            low_since = None
    ok = f.result().success
    log(f'land: {"ok" if ok else "FAILED"} {f.result().message}' + (' (forced disarm)' if forced else ''))
    return ok


def hold():
    """Hold over the tag until a reason to land comes up. Returns that reason, or None if the pilot took over."""
    t0 = s['seen'] = time.time()
    next_log = t0 + 10.0
    while True:
        f = tagnav.call_async(tn_req('hold_on_tag', hold_s=HOLD_CHUNK_S))
        while not f.done():
            rclpy.spin_once(node, timeout_sec=0.05)
            now = time.time()
            if pilot_has_it() or not s['armed']:
                return None
            if s['stop']:
                return f"land requested ({s['stop']})"
            if now - s['seen'] >= LOSS_S:
                return f'tag {TAG} not seen for {now - s["seen"]:.1f} s'
            if HOVER_S > 0 and now - t0 >= HOVER_S:
                return f'hover time {HOVER_S:.0f} s is up'
            if now >= next_log:
                next_log = now + 10.0
                log(f"holding {now - t0:.0f} s: height {s['rng']:.2f} m, tag offset {offset_cm():.1f} cm")
        if not f.result().success:
            return f'hold ended: {f.result().message}'


for c in (flight, tagnav):
    while not c.wait_for_service(timeout_sec=5.0):
        log(f'waiting for {c.srv_name}')
spin(2.0)
log(f'start: hover {HOVER_S:.0f} s, land after {LOSS_S:.0f} s without tag {TAG}, height {TAKEOFF_M} m')
if s['nav'] < 0:
    sys.exit(log('no vehicle status from PX4: not starting') or 1)
if s['armed'] or not s['landed']:
    sys.exit(log('aircraft is armed or not landed: not starting') or 1)
if s['stop']:
    sys.exit(log('stopped before arming') or 1)

if not fc('arm'):
    sys.exit(1)
for _ in range(30):                      # the arm takes a moment to show in vehicle_status
    spin(0.1)
    if s['armed']:
        break
if not s['armed']:
    sys.exit(log('arm command accepted but the aircraft is not armed (PX4 preflight check?): not starting') or 1)
t0 = time.time()
if not fc('offboard_takeoff', value=TAKEOFF_M, timeout=25.0) or s['nav'] != OFFBOARD:
    if not pilot_has_it():
        land('takeoff did not complete')
    sys.exit(1)
log(f"takeoff done: height {s['rng']:.2f} m, {time.time() - t0:.1f} s after arming")
engage.publish(Bool(data=True)); spin(0.3)
if not call(tagnav, tn_req('center_on_tag', timeout=20.0)):
    if not pilot_has_it():
        land(f'could not center on tag {TAG}')
    sys.exit(1)
why = hold()
if why is None:
    log('left Offboard or disarmed without this script: the pilot has it, standing down')
    sys.exit(0)
ok = land(why)
log(f"done {'ok' if ok else 'FAILED'}: {time.time() - t0:.0f} s armed to landed")
