#!/usr/bin/env python3
"""Render a flight bag's tag camera to MP4 with the tag detection and flight state drawn on.

    tools/bag_video.py <bag.mcap> <out.mp4>

Draws the detected tag outline and center, the image center, and a panel with flight time,
flight mode, tag_nav state, rangefinder height, tag error, detection rate and decision margin.
Needs mcap-ros2-support, opencv-python-headless, numpy, and ffmpeg on the PATH.
"""
import bisect, json, math, subprocess, sys
import cv2
import numpy as np
from mcap_ros2.reader import read_ros2_messages

NAV = {0: 'MANUAL', 1: 'ALTCTL', 2: 'POSITION', 3: 'MISSION', 4: 'LOITER', 5: 'RTL', 14: 'OFFBOARD',
       15: 'STAB', 17: 'TAKEOFF', 18: 'LAND', 10: 'ACRO'}
bag, out = sys.argv[1], sys.argv[2]


def stamp(h):
    return h.stamp.sec * 1_000_000_000 + h.stamp.nanosec


# Pass 1: everything but the images.
dets, rate_t, lp, tn, vs = {}, [], [], [], []
for m in read_ros2_messages(bag, topics=['/apriltag_detections', '/fmu/out/vehicle_local_position', '/fmu/out/vehicle_local_position_20hz',
                                         '/dexi/tag_nav/status', '/fmu/out/vehicle_status_v1',
                                         '/fmu/out/vehicle_status']):
    t, r, tp = m.log_time_ns / 1e9, m.ros_msg, m.channel.topic
    if tp == '/apriltag_detections':
        d = [x for x in r.detections if x.id == 0]
        if d:
            dets[stamp(r.header)] = d[0]
            rate_t.append(t)
    elif 'local_position' in tp:
        lp.append((t, r.dist_bottom))
    elif tp == '/dexi/tag_nav/status':
        tn.append((t, json.loads(r.data)))
    else:
        vs.append((t, r.nav_state, r.arming_state == 2))
keys = {k: [x[0] for x in v] for k, v in (('lp', lp), ('tn', tn), ('vs', vs))}


def latest(name, lst, t):
    i = bisect.bisect_right(keys[name], t) - 1
    return lst[i] if i >= 0 else None


ff = None
t0 = None
font = cv2.FONT_HERSHEY_SIMPLEX
for m in read_ros2_messages(bag, topics=['/cam0/image_raw/compressed']):
    t = m.log_time_ns / 1e9
    t0 = t0 or t
    img = cv2.imdecode(np.frombuffer(bytes(m.ros_msg.data), np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    if ff is None:
        ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                               '-s', f'{w}x{h + 120}', '-framerate', '28.6', '-i', '-', '-c:v', 'libx264',
                               '-pix_fmt', 'yuv420p', '-crf', '23', '-movflags', '+faststart', out],
                              stdin=subprocess.PIPE)
    cx, cy = w // 2, h // 2
    cv2.drawMarker(img, (cx, cy), (255, 255, 255), cv2.MARKER_CROSS, 24, 1)
    d = dets.get(stamp(m.ros_msg.header))
    if d:
        pts = np.array([[p.x, p.y] for p in d.corners], np.int32)
        cv2.polylines(img, [pts], True, (0, 220, 0), 2)
        cv2.line(img, (int(pts[2][0]), int(pts[2][1])), (int(pts[3][0]), int(pts[3][1])), (0, 220, 255), 3)  # top edge
        c = (int(d.centre.x), int(d.centre.y))
        cv2.circle(img, c, 5, (0, 220, 0), -1)
        cv2.line(img, (cx, cy), c, (0, 220, 0), 1)

    panel = np.full((120, w, 3), 30, np.uint8)
    v = latest('vs', vs, t)
    n = latest('tn', tn, t)
    l = latest('lp', lp, t)
    st = n[1] if n else {}
    off = st.get('offset') or {}
    err = math.hypot(off.get('forward', 0), off.get('right', 0)) * 100 if off else None
    i1, i0 = bisect.bisect_right(rate_t, t), bisect.bisect_left(rate_t, t - 1.0)
    lines = [
        f"T+{t - t0:6.1f} s   {NAV.get(v[1], v[1]) if v else '?'}   {'ARMED' if v and v[2] else 'disarmed'}",
        f"tag_nav: {st.get('state', '?')}   tag error: {f'{err:4.1f} cm' if err is not None else '  --'}",
        f"range: {l[1]:.2f} m   tag down: {off.get('down', float('nan')):.2f} m" if l else 'range: --',
        f"detections: {i1 - i0} /s   margin: {d.decision_margin:.0f}" if d else f"detections: {i1 - i0} /s",
    ]
    for k, s in enumerate(lines):
        cv2.putText(panel, s, (10, 26 + k * 27), font, 0.6, (235, 235, 235), 1, cv2.LINE_AA)
    ff.stdin.write(np.vstack([img, panel]).tobytes())
ff.stdin.close()
ff.wait()
print('wrote', out)
