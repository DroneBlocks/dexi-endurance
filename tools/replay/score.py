"""score.py <original.ulg> <replayed.ulg> [label]: EKF height vs rangefinder while airborne."""
import sys
import numpy as np
from pyulog import ULog
orig, rep = sys.argv[1], sys.argv[2]; label = sys.argv[3] if len(sys.argv) > 3 else rep
o = ULog(orig, ['distance_sensor', 'vehicle_land_detected', 'vehicle_status'])
r = ULog(rep, ['vehicle_local_position'])
g = lambda u, n: next(d.data for d in u.data_list if d.name == n)
ds, ld, lp = g(o, 'distance_sensor'), g(o, 'vehicle_land_detected'), g(r, 'vehicle_local_position')
ts = lp['timestamp_sample'] if 'timestamp_sample' in lp else lp['timestamp']
t_air = ld['timestamp'][ld['landed'] == 0]
t0, t1 = t_air[0], t_air[-1]
rng = np.interp(ts, ds['timestamp'], ds['current_distance'])
z = lp['z']; air = (ts >= t0 + 0.5e6) & (ts <= t1 - 0.5e6)
# height above the takeoff spot: EKF uses z at liftoff, rangefinder uses its ground reading
i0 = np.searchsorted(ts, t0); g0 = np.median(ds['current_distance'][ds['timestamp'] < t0][-20:])
ekf_h = z[i0] - z; real_h = rng - g0
err = (ekf_h - real_h)[air]
resets = int(np.sum(np.diff(lp['z_reset_counter'][air]) > 0))
climb = air & (ts <= t0 + 8e6)
hold = air & (ts >= t0 + 60e6)
e_h = (ekf_h - real_h)[hold] if hold.any() else err
q = len(e_h) // 10 or 1
print(f"{label:28s} hold: err std {np.std(e_h):4.2f} m, drift {np.mean(e_h[-q:]) - np.mean(e_h[:q]):+5.2f} m  |  ", end='')
print(f"{label:28s} resets {resets:3d}   height error mean {np.mean(err):+5.2f} m  max |err| {np.max(np.abs(err)):4.2f} m  "
      f"first 8 s max {np.max(np.abs((ekf_h - real_h)[climb])):4.2f} m   airborne {(t1 - t0) / 1e6:5.0f} s")
