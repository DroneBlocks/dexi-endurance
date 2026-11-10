#!/usr/bin/env python3
"""5 Hz: EKF height vs rangefinder vs tag, plus EKF height-source flags. Events on any flag change."""
import json, time, math
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
from px4_msgs.msg import VehicleLocalPosition, EstimatorStatusFlags, VehicleStatus
OUT = '/home/dexi/hgt_watch_' + time.strftime('%H%M%S')
rclpy.init(); n = Node('hgt_watch'); s = {}
q = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=1)
n.create_subscription(VehicleLocalPosition, '/fmu/out/vehicle_local_position', lambda m: s.__setitem__('lp', m), q)
n.create_subscription(EstimatorStatusFlags, '/fmu/out/estimator_status_flags', lambda m: s.__setitem__('f', m), q)
n.create_subscription(VehicleStatus, '/fmu/out/vehicle_status_v1', lambda m: s.__setitem__('vs', m), q)
n.create_subscription(VehicleStatus, '/fmu/out/vehicle_status', lambda m: s.__setitem__('vs', m), q)
n.create_subscription(String, '/dexi/tag_nav/status', lambda m: s.__setitem__('tn', json.loads(m.data)), 10)
FL = ['cs_rng_hgt', 'cs_baro_hgt', 'cs_rng_fault', 'cs_rng_kin_consistent', 'cs_rng_stuck', 'cs_rng_terrain',
      'cs_opt_flow', 'cs_opt_flow_terrain', 'reject_ver_pos', 'reject_hagl', 'cs_inertial_dead_reckoning', 'cs_wind_dead_reckoning']
csvf = open(OUT + '.csv', 'w'); ev = open(OUT + '_events.txt', 'w')
csvf.write('t,armed,nav,ekf_up,range,range_valid,vz,tag_down,' + ','.join(FL) + '\n')
prev = {}; t0 = time.time(); nxt = t0
while True:
    rclpy.spin_once(n, timeout_sec=0.02)
    if time.time() < nxt or 'lp' not in s: continue
    nxt += 0.2; lp = s['lp']; f = s.get('f'); vs = s.get('vs'); tn = s.get('tn', {}); off = tn.get('offset') or {}
    fl = {k: int(bool(getattr(f, k, False))) for k in FL} if f else {}
    armed = int(bool(vs and vs.arming_state == 2)); nav = vs.nav_state if vs else -1
    t = time.time() - t0
    csvf.write(f"{t:.1f},{armed},{nav},{-lp.z:.3f},{lp.dist_bottom:.3f},{int(lp.dist_bottom_valid)},{lp.vz:+.3f},{off.get('down')}," + ','.join(str(fl.get(k, '')) for k in FL) + '\n'); csvf.flush()
    cur = dict(fl, armed=armed, nav=nav)
    for k, v in cur.items():
        if prev.get(k) != v:
            ev.write(f"{time.strftime('%H:%M:%S')} t={t:.1f} {k} -> {v}  (ekf {-lp.z:.2f} rng {lp.dist_bottom:.2f} tag {off.get('down')})\n"); ev.flush()
    prev = cur
