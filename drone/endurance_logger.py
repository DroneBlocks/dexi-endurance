#!/usr/bin/env python3
"""Endurance logger: 1 Hz samples + a one-minute analysis line, written on the drone.

Out: /home/dexi/endurance/<start>/samples.csv, minutes.csv, report.txt
"""
import csv, json, math, os, statistics as st, subprocess, threading, time, urllib.request
from datetime import datetime
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from std_msgs.msg import String
from px4_msgs.msg import BatteryStatus, VehicleLocalPosition, VehicleStatus

NAV = {0: 'Manual', 1: 'Altitude', 2: 'Position', 4: 'Hold', 14: 'Offboard', 15: 'Stabilized', 17: 'Takeoff', 18: 'Land'}
RUN = datetime.now().strftime('%Y-%m-%d_%H%M%S')
OUT = f'/home/dexi/endurance/{RUN}'
os.makedirs(OUT, exist_ok=True)
M2R = 'http://127.0.0.1:8088/v1/mavlink/vehicles/1/components/1/messages/'

def m2r(name):
    try:
        with urllib.request.urlopen(M2R + name, timeout=0.5) as r:
            return json.load(r)['message']
    except Exception:
        return None

def sh(cmd):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2).stdout.strip()
    except Exception: return ''

def pct(a, p):
    if not a: return float('nan')
    a = sorted(a); return a[min(len(a) - 1, int(round(p / 100 * (len(a) - 1))))]

_round = round
def round(x, n=None):
    try:
        if isinstance(x, float) and math.isnan(x): return x
        return _round(x, n) if n is not None else _round(x)
    except Exception:
        return x

_cpu_prev = [None]
def cpu_pct():
    v = list(map(int, open('/proc/stat').readline().split()[1:]))
    idle, tot = v[3] + v[4], sum(v)
    p = _cpu_prev[0]; _cpu_prev[0] = (idle, tot)
    if not p or tot == p[1]: return float('nan')
    return 100.0 * (1 - (idle - p[0]) / (tot - p[1]))

def mean(a): return st.fmean(a) if a else float('nan')

class Logger(Node):
    def __init__(self):
        super().__init__('endurance_logger')
        be = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                        history=HistoryPolicy.KEEP_LAST, depth=1)
        self.tn = None; self.bat = None; self.lp = None; self.vs = None
        self.create_subscription(String, '/dexi/tag_nav/status', lambda m: setattr(self, 'tn', json.loads(m.data)), 10)
        self.create_subscription(BatteryStatus, '/fmu/out/battery_status', lambda m: setattr(self, 'bat', m), be)
        self.create_subscription(VehicleLocalPosition, '/fmu/out/vehicle_local_position_20hz', lambda m: setattr(self, 'lp', m), be)  # 20 Hz copy: the 100 Hz topic cost ~half a core in Python
        self.create_subscription(VehicleStatus, '/fmu/out/vehicle_status_v1', lambda m: setattr(self, 'vs', m), be)
        self.create_subscription(VehicleStatus, '/fmu/out/vehicle_status', lambda m: setattr(self, 'vs', m), be)

def main():
    rclpy.init()
    n = Logger()
    threading.Thread(target=rclpy.spin, args=(n,), daemon=True).start()
    cols = ['t', 'clock', 'mode', 'armed', 'tn_state', 'engaged', 'visible', 'off_fwd', 'off_right', 'err_m',
            'range_m', 'range_valid', 'ekf_x', 'ekf_y', 'ekf_z', 'heading_deg', 'vxy',
            'bat_v', 'bat_a', 'bat_w', 'bat_pct', 'bat_mah', 'bat_warn',
            'rpm1', 'rpm2', 'rpm3', 'rpm4', 'esc_a1', 'esc_a2', 'esc_a3', 'esc_a4', 'esc_t1', 'esc_t2', 'esc_t3', 'esc_t4', 'esc_err',
            'z_resets', 'fc_load', 'pi_temp', 'pi_throttled', 'pi_load1', 'pi_mem_pct', 'pi_cpu_pct']
    sf = open(f'{OUT}/samples.csv', 'w', newline=''); sw = csv.writer(sf); sw.writerow(cols)
    mcols = ['minute', 'clock', 'airborne_s', 'modes', 'offboard_pct', 'tag_visible_pct', 'err_mean_cm', 'err_rms_cm', 'err_p95_cm', 'err_max_cm',
             'range_mean_m', 'range_std_cm', 'heading_drift_deg', 'ekf_drift_m', 'bat_v_min', 'bat_v_mean', 'bat_a_mean', 'bat_w_mean', 'wh_total',
             'rpm_mean', 'rpm_spread_pct', 'esc_a_mean', 'esc_t_max', 'esc_err', 'hgt_resets', 'fc_load_pct', 'pi_temp_max', 'pi_throttled', 'pi_load1', 'pi_cpu_mean', 'pi_cpu_max', 'pi_mem_max']
    mf = open(f'{OUT}/minutes.csv', 'w', newline=''); mw = csv.writer(mf); mw.writerow(mcols)
    rep = open(f'{OUT}/report.txt', 'a')
    rep.write(f'DEXI-5 endurance run {RUN} (tethered, hold over tag 0 via CH7 Offboard)\n'); rep.flush()

    t0 = time.time(); win = []; minute = 0; wh = 0.0; airborne_total = 0.0
    hdg0 = None; ekf0 = None; last_t = t0; thr = ''
    while True:
        tick = time.time()
        tn = n.tn or {}; b = n.bat; lp = n.lp; vs = n.vs
        esc = m2r('ESC_STATUS') or {}; info = m2r('ESC_INFO') or {}; sys_ = m2r('SYS_STATUS') or {}
        off = tn.get('offset') or {}
        f_, r_ = off.get('forward'), off.get('right')
        err = math.hypot(f_, r_) if f_ is not None and r_ is not None else None
        mode = NAV.get(vs.nav_state, str(vs.nav_state)) if vs else ''
        armed = bool(vs and vs.arming_state == VehicleStatus.ARMING_STATE_ARMED)
        bv = b.voltage_v if b else float('nan'); ba = b.current_a if b else float('nan')
        bw = bv * ba if b and ba >= 0 else float('nan')
        dt = tick - last_t; last_t = tick
        if armed and not math.isnan(bw): wh += bw * dt / 3600
        rng = lp.dist_bottom if lp else float('nan')
        hdg = math.degrees(lp.heading) % 360 if lp else float('nan')
        rpm = list(esc.get('rpm', [0] * 4))[:4]; ea = list(esc.get('current', [0] * 4))[:4]
        et = [x / 100 for x in info.get('temperature', [0] * 4)][:4]
        eerr = sum(info.get('error_count', [0])) if info else 0
        load1 = os.getloadavg()[0]
        temp = f"{int(open('/sys/class/thermal/thermal_zone0/temp').read()) / 1000:.1f}"
        if int(tick) % 10 == 0 or not thr:      # vcgencmd forks a process: every 10 s is enough
            thr = sh('vcgencmd get_throttled').replace('throttled=', '')
        mi = dict(l.split(':', 1) for l in open('/proc/meminfo'))
        kb = lambda k: int(mi[k].split()[0])
        mem = f"{100 * (1 - kb('MemAvailable') / kb('MemTotal')):.0f}"
        row = dict(t=round(tick - t0, 1), clock=datetime.now().strftime('%H:%M:%S'), mode=mode, armed=int(armed),
                   tn_state=tn.get('state'), engaged=int(bool(tn.get('engaged'))), visible=int(bool(tn.get('visible'))),
                   off_fwd=f_, off_right=r_, err_m=None if err is None else round(err, 3),
                   range_m=round(rng, 3), range_valid=int(bool(lp and 0.2 < lp.dist_bottom < 10)),
                   ekf_x=round(lp.x, 3) if lp else None, ekf_y=round(lp.y, 3) if lp else None, ekf_z=round(lp.z, 3) if lp else None,
                   heading_deg=round(hdg, 1), vxy=round(math.hypot(lp.vx, lp.vy), 3) if lp else None,
                   bat_v=round(bv, 2), bat_a=round(ba, 2), bat_w=round(bw, 1), bat_pct=round(b.remaining * 100, 1) if b else None,
                   bat_mah=round(b.discharged_mah) if b else None, bat_warn=b.warning if b else None,
                   rpm1=rpm[0], rpm2=rpm[1], rpm3=rpm[2], rpm4=rpm[3],
                   esc_a1=round(ea[0], 2), esc_a2=round(ea[1], 2), esc_a3=round(ea[2], 2), esc_a4=round(ea[3], 2),
                   esc_t1=et[0], esc_t2=et[1], esc_t3=et[2], esc_t4=et[3], esc_err=eerr,
                   z_resets=lp.z_reset_counter if lp else None, fc_load=round(sys_.get('load', 0) / 10, 1), pi_temp=temp, pi_throttled=thr, pi_load1=round(load1, 2), pi_mem_pct=mem, pi_cpu_pct=round(cpu_pct(), 1))
        sw.writerow([row[c] for c in cols]); sf.flush()
        win.append(row)
        if armed and row['range_valid'] and rng > 0.3: airborne_total += dt

        if tick - t0 >= (minute + 1) * 60:
          minute += 1
          try:
              ob = [r for r in win if r['mode'] == 'Offboard']
              errs = [r['err_m'] * 100 for r in ob if r['err_m'] is not None and r['visible']]
              rngs = [r['range_m'] for r in win if r['range_valid'] and r['armed']]
              hd = [r['heading_deg'] for r in ob if not math.isnan(r['heading_deg'])]
              if hd and hdg0 is None: hdg0 = hd[0]
              hdrift = ((hd[-1] - hdg0 + 180) % 360 - 180) if hd and hdg0 is not None else float('nan')
              xy = [(r['ekf_x'], r['ekf_y']) for r in ob if r['ekf_x'] is not None]
              if xy and ekf0 is None: ekf0 = xy[0]
              edrift = math.hypot(xy[-1][0] - ekf0[0], xy[-1][1] - ekf0[1]) if xy and ekf0 else float('nan')
              vs_ = [r['bat_v'] for r in win if not math.isnan(r['bat_v'])]
              arm = [r for r in win if r['armed']]
              rpms = [mean([r[f'rpm{i}'] for r in arm]) for i in range(1, 5)] if arm else []
              rpm_m = mean(rpms) if rpms else float('nan')
              spread = (max(rpms) - min(rpms)) / rpm_m * 100 if rpms and rpm_m else float('nan')
              modes = '/'.join(sorted({r['mode'] for r in win if r['mode']}))
              temps = [float(r['pi_temp']) for r in win if r['pi_temp']]
              thrs = sorted({r['pi_throttled'] for r in win if r['pi_throttled']})
              m = dict(minute=minute, clock=row['clock'], airborne_s=round(airborne_total), modes=modes,
                       offboard_pct=round(100 * len(ob) / len(win)), tag_visible_pct=round(100 * sum(r['visible'] for r in ob) / len(ob)) if ob else 0,
                       err_mean_cm=round(mean(errs), 1), err_rms_cm=round(math.sqrt(mean([e * e for e in errs])), 1) if errs else float('nan'),
                       err_p95_cm=round(pct(errs, 95), 1), err_max_cm=round(max(errs), 1) if errs else float('nan'),
                       range_mean_m=round(mean(rngs), 3), range_std_cm=round(st.pstdev(rngs) * 100, 1) if len(rngs) > 1 else float('nan'),
                       heading_drift_deg=round(hdrift, 1), ekf_drift_m=round(edrift, 2),
                       bat_v_min=round(min(vs_), 2) if vs_ else float('nan'), bat_v_mean=round(mean(vs_), 2),
                       bat_a_mean=round(mean([r['bat_a'] for r in arm]), 2), bat_w_mean=round(mean([r['bat_w'] for r in arm if not math.isnan(r['bat_w'])]), 1),
                       wh_total=round(wh, 1), rpm_mean=round(rpm_m), rpm_spread_pct=round(spread, 1),
                       esc_a_mean=round(mean([sum(r[f'esc_a{i}'] for i in range(1, 5)) for r in arm]), 2),
                       esc_t_max=max(max(r[f'esc_t{i}'] for i in range(1, 5)) for r in win), esc_err=row['esc_err'], hgt_resets=(lambda zs: (int(zs[-1]) - int(zs[0])) % 256 if zs else None)([r['z_resets'] for r in win if r['z_resets'] is not None]),
                       fc_load_pct=round(mean([r['fc_load'] for r in win]), 1), pi_temp_max=max(temps) if temps else float('nan'),
                       pi_throttled=','.join(thrs), pi_load1=round(mean([r['pi_load1'] for r in win]), 2), pi_cpu_mean=round(mean([r['pi_cpu_pct'] for r in win if r['pi_cpu_pct'] == r['pi_cpu_pct']]), 1), pi_cpu_max=max([r['pi_cpu_pct'] for r in win if r['pi_cpu_pct'] == r['pi_cpu_pct']] or [float('nan')]), pi_mem_max=max([int(r['pi_mem_pct']) for r in win if str(r['pi_mem_pct']).isdigit()] or [0]))
              mw.writerow([m[c] for c in mcols]); mf.flush()
              rep.write(f"[{m['clock']}] min {minute:>3} | air {int(m['airborne_s']) // 60}m{int(m['airborne_s']) % 60:02d}s | {modes} off {m['offboard_pct']}% tag {m['tag_visible_pct']}% "
                        f"| err mean {m['err_mean_cm']} p95 {m['err_p95_cm']} max {m['err_max_cm']} cm | alt {m['range_mean_m']} m ±{m['range_std_cm']} cm "
                        f"| hdg {m['heading_drift_deg']}° ekf {m['ekf_drift_m']} m | {m['bat_v_min']}-{m['bat_v_mean']} V {m['bat_a_mean']} A {m['bat_w_mean']} W {m['wh_total']} Wh "
                        f"| rpm {m['rpm_mean']} ±{m['rpm_spread_pct']}% ESC {m['esc_t_max']}°C err {m['esc_err']} | hgt resets {m['hgt_resets']} | FC {m['fc_load_pct']}% Pi {m['pi_temp_max']}°C thr {m['pi_throttled']} ld {m['pi_load1']} CPU {m['pi_cpu_mean']}% (max {m['pi_cpu_max']}) mem {m['pi_mem_max']}%\n")
              rep.flush(); win = []
          except Exception as e:
            rep.write(f"[min {minute}] summary error: {e!r}\n"); rep.flush(); win = []
        time.sleep(max(0.0, 1.0 - (time.time() - tick)))

if __name__ == '__main__':
    main()
