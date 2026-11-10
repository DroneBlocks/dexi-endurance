#!/usr/bin/env python3
"""Dump or check PX4 parameters over MAVLink (GCS port 14550 via mavlink-router).

    tools/params.py dump  airframes/dexi5.yaml > runs/<run>/params.txt
    tools/params.py check airframes/dexi5.yaml          # exit 1 on any mismatch

Needs pymavlink and PyYAML. Host comes from DEXI_HOST or the profile's `host`.
"""
import os, struct, sys, time
import yaml
from pymavlink import mavutil

INT_TYPES = range(1, 9)    # MAV_PARAM_TYPE UINT8..INT64 arrive bit-packed in a float


def value(msg):
    if msg.param_type in INT_TYPES:
        return struct.unpack('<i', struct.pack('<f', msg.param_value))[0]
    return round(msg.param_value, 6)


def connect(profile):
    host = os.environ.get('DEXI_HOST') or profile['host']
    m = mavutil.mavlink_connection(f'udpout:{host}:14550', source_system=254)
    m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS, mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
    if not m.wait_heartbeat(timeout=10):
        sys.exit(f'no heartbeat from {host}:14550')
    return m


def dump(m):
    m.mav.param_request_list_send(m.target_system, 1)
    got, total, last = {}, None, time.time()
    while time.time() - last < 3 and (total is None or len(got) < total):
        msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=1)
        if msg:
            got[msg.param_id] = value(msg); total = msg.param_count; last = time.time()
    for name in sorted(got):
        print(f'{name}\t{got[name]}')
    if total and len(got) < total:
        print(f'# WARNING: received {len(got)} of {total} parameters', file=sys.stderr)


def get(m, name):
    for _ in range(3):
        m.mav.param_request_read_send(m.target_system, 1, name.encode(), -1)
        end = time.time() + 1.5
        while time.time() < end:
            msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.5)
            if msg and msg.param_id == name:
                return value(msg)
    return None


def check(m, expected):
    bad = 0
    for name, want in expected.items():
        have = get(m, name)
        ok = have is not None and abs(float(have) - float(want)) < 1e-4
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name:18} {have!s:>8}  (want {want})")
    return bad


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('dump', 'check'):
        sys.exit(__doc__)
    profile = yaml.safe_load(open(sys.argv[2]))
    m = connect(profile)
    if sys.argv[1] == 'dump':
        dump(m)
    else:
        sys.exit(1 if check(m, profile['params']) else 0)
